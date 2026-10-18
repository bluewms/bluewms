from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        pending = self.filtered(lambda picking: picking.state != 'done')
        result = super().button_validate()
        for picking in pending.filtered(lambda picking: picking.state == 'done'):
            tasks = picking.wcs_request_ids.filtered(lambda task: task.protocol_release_id
                and task.state == 'completed' and task.protocol_subposition).sorted(lambda task: (task.done_date, task.step, task.id))
            # Native quant updates may clear the temporary empty package during a move.
            # Restore only the approved completed event for this just-validated picking.
            for task in tasks:
                task._protocol_packages().write({'package_removal_priority': task.protocol_subposition})
        return result
