import { Component, onMounted, proxy, signal, t, useProps } from '@odoo/owl';

/** Dedicated terminal quantity screen, following the 16 app's keypad workflow. */
export class QuantityEditor extends Component {
    static template = 'blue_barcode_base.QuantityEditor';
    props = useProps({
        row: t.any(), inventory: t.boolean(),
        onConfirm: t.function(), onCancel: t.function(),
    });

    setup() {
        this.state = proxy({value: String(this.props.inventory && !this.props.row.counted ? 0 : this.props.row.quantity),
            replace: true, error: ''});
        this.input = signal.ref();
        onMounted(() => {
            this.input()?.focus();
            this.input()?.select();
        });
    }

    key(value) {
        this.state.error = '';
        if (value === 'clear') {
            this.state.value = '0';
            this.state.replace = true;
        } else if (value === 'back') {
            this.state.value = this.state.value.slice(0, -1) || '0';
            this.state.replace = false;
        } else if (value === '+1' || value === '-1') {
            this.state.value = String(Math.max(0, Number((Number(this.state.value) + Number(value)).toFixed(8))));
            this.state.replace = true;
        } else {
            let current = this.state.replace ? '' : this.state.value;
            if (value === '.' && current.includes('.')) {
                return;
            }
            if (current === '0' && value !== '.') {
                current = '';
            }
            this.state.value = current + value;
            if (this.state.value === '.') {
                this.state.value = '0.';
            }
            this.state.replace = false;
        }
    }

    confirm() {
        const value = Number(this.state.value);
        if (!/^\d+(?:\.\d+)?$/.test(this.state.value) || !Number.isFinite(value) || value > 1e9) {
            this.state.error = '请输入有效的非负总数';
            return;
        }
        this.props.onConfirm(value);
    }

    keydown(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            this.confirm();
        } else if (event.key === 'Escape') {
            this.props.onCancel();
        }
    }
}
