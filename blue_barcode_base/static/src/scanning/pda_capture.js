/** Lossless PDA collection. Emits through Odoo's barcode bus, never edits stock. */
export class PdaCapture {
    constructor({ emit, isActive, input = null, delay = 150, timers = globalThis }) {
        this.emit = emit;
        this.isActive = isActive;
        this.input = input;
        this.delay = delay;
        this.timers = timers;
        this.buffer = '';
        this.keydown = this.keydown.bind(this);
        this.inputEvent = this.inputEvent.bind(this);
        this.reset = this.reset.bind(this);
    }

    attach(target = window) {
        this.target = target;
        target.addEventListener('keydown', this.keydown, true);
        target.addEventListener('input', this.inputEvent, true);
        target.addEventListener('blur', this.reset);
    }

    destroy() {
        this.target?.removeEventListener('keydown', this.keydown, true);
        this.target?.removeEventListener('input', this.inputEvent, true);
        this.target?.removeEventListener('blur', this.reset);
        this.reset();
    }

    editable(target) {
        return target !== this.input && target?.closest?.('input, textarea, select, [contenteditable="true"]');
    }

    reset() {
        this.timers.clearTimeout(this.timer);
        this.buffer = '';
        if (this.input) {
            this.input.value = '';
        }
    }

    schedule() {
        this.timers.clearTimeout(this.timer);
        this.timer = this.timers.setTimeout(() => this.flush(), this.delay);
    }

    flush(event) {
        const raw = this.input?.value || this.buffer;
        this.reset();
        if (raw && this.isActive()) {
            event?.preventDefault();
            this.emit(raw.replace(/[\r\n\t]+$/, ''));
        }
    }

    keydown(event) {
        if (!this.isActive() || this.editable(event.target) || event.isComposing || !event.key) {
            this.reset();
            return;
        }
        if (['Control', 'Alt', 'Shift'].includes(event.key)) {
            event.stopPropagation();
            return;
        }
        if (event.ctrlKey && event.key === ']') {
            event.stopPropagation();
            event.preventDefault();
            if (event.target === this.input) {
                this.input.value += '\x1d';
            } else {
                this.buffer += '\x1d';
            }
            this.schedule();
            return;
        }
        if (event.metaKey || event.ctrlKey || event.altKey) {
            return;
        }
        if (['Enter', 'Tab'].includes(event.key)) {
            if (this.buffer || this.input?.value) {
                event.stopPropagation();
                this.flush(event);
            }
        } else if (event.key.length === 1) {
            event.stopPropagation();
            if (event.target !== this.input) {
                event.preventDefault();
                this.buffer += event.key;
                this.schedule();
            }
        }
    }

    inputEvent(event) {
        if (!this.input || event.target !== this.input || !this.isActive()) {
            return;
        }
        event.stopPropagation();
        if (/[\r\n\t]$/.test(this.input.value)) {
            this.flush();
        } else {
            this.schedule();
        }
    }
}
