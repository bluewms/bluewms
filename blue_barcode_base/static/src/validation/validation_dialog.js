import { Component, proxy, t, useProps } from '@odoo/owl';
import { Dialog } from '@web/core/dialog/dialog';

export class ValidationDialog extends Component {
    static template = 'blue_barcode_base.ValidationDialog';
    static components = { Dialog };
    props = useProps({review: t.any(), confirm: t.function(), close: t.function()});

    setup() {
        this.state = proxy({busy: false});
    }

    missing() {
        return this.props.review.lines.filter((line) => !line.complete);
    }

    async confirm() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.props.close();
        await this.props.confirm();
    }
}
