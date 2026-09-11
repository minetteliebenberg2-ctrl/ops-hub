"""Register the Annual Compliance module with FC Hub."""

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class AnnualComplianceUtility(BaseModule):

    module_info = ModuleInfo(
        module_id="annual_compliance",
        name="Annual Compliance",
        description="COIDA returns, payslip generator, and annual financial records.",
        category="Compliance",
        sort_order=90,
        icon="FileCheck",
    )

    def __init__(self):
        super().__init__()

    def create_window(self, master):
        from modules.annual_compliance.windows import AnnualComplianceWindow
        return AnnualComplianceWindow(master)
