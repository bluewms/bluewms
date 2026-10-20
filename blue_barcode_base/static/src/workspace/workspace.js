import {
    Component, onMounted, onWillDestroy, onWillStart, proxy, signal, useListener, useProps,
} from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { standardActionServiceProps } from '@web/webclient/actions/action_plugin';
import { scanBarcode } from '@web/core/barcode/barcode_dialog';
import { user } from '@web/core/user';

function identity() {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    return [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

export class BarcodeWorkspace extends Component {
    static template = 'blue_barcode_base.Workspace';
    props = useProps({ ...standardActionServiceProps });
    scanInput = signal.ref();

    setup() {
        this.orm = useService('orm');
        this.action = useService('action');
        this.notification = useService('notification');
        this.state = proxy({
            entries: [], page: 'home', listKind: '', items: [], more: false, offset: 0,
            search: '', raw: '', session: null, details: null, group: '', selected: '',
            editing: false, total: '', error: '', storageError: '', busy: false, pending: null, queued: 0, message: '',
        });
        this.companyId = user.activeCompanies[0].id;
        this.storageKey = `blue_barcode_${user.userId}_${this.companyId}`;
        this.client = identity();
        try {
            this.client = sessionStorage.getItem(`${this.storageKey}_client`) || this.client;
            sessionStorage.setItem(`${this.storageKey}_client`, this.client);
        } catch (error) {
            this.state.storageError = '终端无法保存恢复信息，扫码已暂停。请恢复浏览器存储后重试。';
        }
        this.queue = [];
        this.buffer = '';
        useListener(document, 'keydown', (event) => this.onScannerKey(event));
        onWillDestroy(() => clearTimeout(this.bufferTimer));
        onWillStart(async () => {
            this.state.entries = await this.orm.call('blue.barcode.service', 'menu_entries', []);
            const params = this.props.action.params || {};
            if (params.kind && params.record_id) {
                await this.openRecord({ kind: params.kind, id: params.record_id });
            } else {
                let saved;
                try {
                    saved = sessionStorage.getItem(this.storageKey);
                } catch (error) {
                    this.state.storageError = '终端无法读取恢复信息，扫码已暂停。';
                }
                if (saved) {
                    let data;
                    try {
                        data = JSON.parse(saved);
                        this.state.pending = data.pending;
                        this.queue = data.queue || [];
                        this.state.queued = this.queue.length;
                        this.acceptView(await this.orm.call('blue.barcode.session', 'action_view', [
                            [data.sessionId], this.client,
                        ]));
                        if (data.pending) {
                            this.state.error = '有上次尚未确认的扫描，请按原事件重试核对结果。';
                        }
                    } catch (error) {
                        if (data?.sessionId) {
                            this.state.session = { id: data.sessionId, name: '待核对扫描会话',
                                kind: 'recovery', state: 'closed', revision: 0, rows: [], context: {}, actions: [] };
                            this.state.page = 'work';
                        }
                        this.state.error = '原会话已变化，请先核对原事件；权限已变更时请联系管理员核对，避免重新扫码计数。';
                    }
                }
            }
        });
        onMounted(() => this.focusScan());
    }

    focusScan() {
        if (!this.state.editing) {
            requestAnimationFrame(() => this.scanInput()?.focus());
        }
    }

    error(error) {
        this.state.error = error.data?.message || error.message || '处理失败，请核对后重试。';
    }

    persist() {
        try {
            sessionStorage.setItem(`${this.storageKey}_client`, this.client);
            if (this.state.session) {
                sessionStorage.setItem(this.storageKey, JSON.stringify({
                    sessionId: this.state.session.id, pending: this.state.pending, queue: this.queue,
                }));
            }
            this.state.storageError = '';
            return true;
        } catch (error) {
            this.state.storageError = '终端恢复信息未能保存，已暂停后续扫描。请恢复浏览器存储后重试。';
            return false;
        }
    }

    acceptView(view) {
        this.state.session = view;
        this.state.page = 'work';
        const groups = this.groups();
        if (!groups.some((group) => group.key === this.state.group)) {
            this.state.group = groups[0]?.key || '';
        }
        if (!view.rows.some((row) => row.key === this.state.selected)) {
            this.state.selected = '';
        }
        this.persist();
    }

    groups() {
        const groups = new Map();
        for (const row of this.state.session?.rows || []) {
            if (!groups.has(row.group)) {
                groups.set(row.group, {
                    key: row.group, source: row.source, destination: row.destination,
                    package: row.package, destinationPackage: row.destination_package,
                    picking: row.picking, rows: [],
                });
            }
            groups.get(row.group).rows.push(row);
        }
        return [...groups.values()];
    }

    currentGroup() {
        return this.groups().find((group) => group.key === this.state.group);
    }

    currentIndex() {
        return this.groups().findIndex((group) => group.key === this.state.group);
    }

    changeGroup(delta) {
        if (this.state.editing) {
            this.state.error = '请先确认或取消手工数量编辑。';
            return;
        }
        const groups = this.groups();
        const index = this.currentIndex() + delta;
        if (index >= 0 && index < groups.length) {
            this.state.group = groups[index].key;
            this.state.selected = '';
        }
        this.focusScan();
    }

    async list(kind, reset = true) {
        if (this.state.pending || this.queue.length) {
            this.state.error = '请先核对尚未确认的扫描。';
            return;
        }
        try {
            if (reset) {
                this.state.offset = 0;
            }
            const result = await this.orm.call('blue.barcode.service', 'list_records', [
                kind, this.state.search, this.state.offset,
            ]);
            this.state.page = 'list';
            this.state.listKind = kind;
            this.state.items = reset ? result.items : [...this.state.items, ...result.items];
            this.state.more = result.more;
            this.state.message = result.message || '';
            this.state.error = '';
        } catch (error) {
            this.error(error);
        }
    }

    async more() {
        this.state.offset += 50;
        await this.list(this.state.listKind, false);
    }

    async openRecord(record, takeover = false) {
        try {
            if (['product', 'location'].includes(record.kind)) {
                this.state.details = await this.orm.call('blue.barcode.service', 'details', [record.kind, record.id]);
                this.state.page = 'details';
            } else {
                if (this.state.pending || this.queue.length) {
                    throw new Error('请先核对尚未确认的扫描。');
                }
                const view = await this.orm.call('blue.barcode.service', 'open_session', [
                    record.kind, record.id, this.client, takeover,
                ]);
                this.acceptView(view);
            }
            this.state.error = '';
            this.focusScan();
        } catch (error) {
            this.error(error);
            this.takeoverRecord = record;
        }
    }

    async takeover() {
        if (this.takeoverRecord && window.confirm('确认接管此作业？原终端将不能继续写入。')) {
            await this.openRecord(this.takeoverRecord, true);
        }
    }

    onScannerKey(event) {
        if (event.target.closest('input, textarea, select, [contenteditable]')
            || document.querySelector('.modal.show') || this.state.editing || document.hidden) {
            return;
        }
        if (event.key === 'Enter' || event.key === 'Tab') {
            if (this.buffer) {
                event.preventDefault();
                const raw = this.buffer;
                this.buffer = '';
                clearTimeout(this.bufferTimer);
                this.submitRaw(raw);
            }
        } else if (event.key.length === 1 && !event.metaKey && !event.ctrlKey) {
            this.buffer += event.key;
            clearTimeout(this.bufferTimer);
            this.bufferTimer = setTimeout(() => { this.buffer = ''; }, 250);
        }
    }

    onInputKey(event) {
        if (['Enter', 'Tab'].includes(event.key)) {
            event.preventDefault();
            this.submitInput();
        }
    }

    submitInput() {
        const raw = this.state.raw;
        this.state.raw = '';
        this.submitRaw(raw);
    }

    async submitRaw(raw) {
        if (!raw || this.state.editing || this.state.storageError) {
            return;
        }
        if (raw.length > 8192 || this.queue.length >= 50) {
            this.state.error = '输入过长或待处理队列已满，当前这次尚未计数。请先核对队列后重新扫描。';
            return;
        }
        if (this.state.page !== 'work') {
            try {
                const matches = await this.orm.call('blue.barcode.service', 'lookup', [raw]);
                if (matches.length === 1) {
                    await this.openRecord(matches[0]);
                } else {
                    this.state.page = 'list';
                    this.state.listKind = 'lookup';
                    this.state.items = matches;
                    this.state.more = false;
                    this.state.error = matches.length ? '编码有多个匹配，请选择。' : '未找到对应单据、产品或位置。';
                }
            } catch (error) {
                this.error(error);
            }
            return;
        }
        if (this.state.pending && !this.state.busy) {
            this.state.error = '有待核对事件，请先重试或核对它。';
            return;
        }
        this.queue.push({ key: identity(), payload: {
            raw, row_key: this.state.selected, group: this.state.group,
        } });
        this.state.queued = this.queue.length;
        this.persist();
        await this.drain();
    }

    async drain() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            while (this.queue.length && !this.state.error) {
                const event = this.queue.shift();
                this.state.queued = this.queue.length;
                this.state.pending = event;
                if (!this.persist()) {
                    break;
                }
                await this.sendEvent(event);
            }
        } catch (error) {
            this.error(error);
            this.persist();
        } finally {
            this.state.busy = false;
            this.focusScan();
        }
        if (!this.state.pending && !this.state.error && !this.queue.length && this.nextAction) {
            const next = this.nextAction;
            this.nextAction = '';
            if (next === 'next_group') {
                this.changeGroup(1);
            } else {
                await this.execute(next);
            }
        }
    }

    async sendEvent(event) {
        const response = await this.orm.call('blue.barcode.session', 'action_event', [
            [this.state.session.id], this.client, event.key, this.state.session.revision, event.payload,
        ]);
        this.state.pending = null;
        this.state.error = '';
        this.acceptView(response.view);
        if (response.event.group && this.state.group === event.payload.group) {
            this.state.group = response.event.group;
        }
        this.nextAction = response.replayed ? '' : response.event.after || '';
        this.state.selected = '';
        this.state.message = response.event.selected || (
            response.event.quantity !== undefined ? `已保存数量：${response.event.quantity}` : '已确认'
        );
        if (response.event.group && response.event.group !== event.payload.group) {
            this.state.message += '（已定位到匹配的业务组）';
        }
        this.persist();
    }

    async cancelPendingProduct() {
        if (this.state.pending || this.state.busy || this.queue.length) {
            return;
        }
        try {
            this.acceptView(await this.orm.call('blue.barcode.session', 'cancel_pending_product', [
                [this.state.session.id], this.client, this.state.session.revision,
            ]));
            this.state.error = '';
            this.state.message = '已取消待补扫产品，没有增加数量。';
        } catch (error) {
            this.error(error);
        }
    }

    async retry() {
        if (!this.state.pending || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            if (!this.persist()) {
                return;
            }
            await this.sendEvent(this.state.pending);
        } catch (error) {
            this.error(error);
        } finally {
            this.state.busy = false;
        }
        if (!this.state.pending) {
            await this.drain();
        }
    }

    async discardRejected() {
        if (!this.state.pending || this.state.busy) {
            return;
        }
        try {
            const response = await this.orm.call('blue.barcode.session', 'event_status', [
                [this.state.session.id], this.client, this.state.pending.key,
            ]);
            this.state.pending = null;
            this.acceptView(response.view);
            this.state.error = this.queue.length ? '后续输入已暂停，请核对当前步骤后明确继续，或取消后重新扫描。' : '';
            this.state.message = response.found ? '该事件已保存，请核对数量。' : '此事件未保存，已取消输入。';
            this.persist();
        } catch (error) {
            this.error(error);
        }
    }

    async continueQueue() {
        if (!this.state.pending && !this.state.busy) {
            this.state.error = '';
            await this.drain();
        }
    }

    cancelQueue() {
        if (!this.state.busy && window.confirm(`确认取消 ${this.queue.length} 条尚未提交的输入？请重新扫描这些货物。`)) {
            this.queue = [];
            this.state.queued = 0;
            this.state.error = '';
            this.persist();
        }
    }

    async camera() {
        try {
            const raw = await scanBarcode(this.env);
            if (raw) {
                await this.submitRaw(raw);
            }
        } catch (error) {
            this.error(error);
        }
    }

    editTotal(row) {
        if (this.state.pending || this.state.busy) {
            return;
        }
        this.state.selected = row.key;
        this.state.total = String(row.quantity);
        this.state.editing = true;
    }

    async saveTotal() {
        if (!/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(this.state.total)) {
            this.state.error = '请输入明确的非负实盘总数。';
            return;
        }
        this.queue.push({ key: identity(), payload: {
            row_key: this.state.selected, total: Number(this.state.total), group: this.state.group,
        } });
        this.state.queued = this.queue.length;
        this.state.editing = false;
        this.state.error = '';
        await this.drain();
    }

    async execute(action) {
        if (this.state.pending || this.state.busy || this.queue.length || this.state.editing) {
            return;
        }
        this.state.busy = true;
        try {
            const response = await this.orm.call('blue.barcode.session', 'action_execute', [
                [this.state.session.id], this.client, this.state.session.revision, action, this.state.group,
            ]);
            this.acceptView(response.view);
            this.state.message = response.message || '已处理，请核对单据状态。';
            if (response.action) {
                await this.action.doAction(response.action, { onClose: () => this.afterNativeAction() });
            }
        } catch (error) {
            this.error(error);
        } finally {
            this.state.busy = false;
        }
    }

    async afterNativeAction() {
        try {
            const view = await this.orm.call('blue.barcode.session', 'action_view', [[this.state.session.id], this.client]);
            this.acceptView(view);
            if (view.state === 'active') {
                await this.orm.call('blue.barcode.session', 'action_release', [[view.id], this.client]);
                await this.openRecord({kind: view.kind, id: view.record_id});
            }
        } catch (error) {
            this.error(error);
        }
    }

    async home() {
        if (this.state.pending || this.state.busy || this.state.editing || this.queue.length) {
            this.state.error = '请先确认当前输入和待处理扫描。';
            return;
        }
        try {
            if (this.state.session) {
                await this.orm.call('blue.barcode.session', 'action_release', [[this.state.session.id], this.client]);
            }
            this.state.session = null;
            this.state.page = 'home';
            this.state.error = '';
            this.state.message = '';
            this.state.search = '';
            sessionStorage.removeItem(this.storageKey);
        } catch (error) {
            this.error(error);
        }
    }
}

registry.category('actions').add('blue_barcode.workspace', BarcodeWorkspace);
