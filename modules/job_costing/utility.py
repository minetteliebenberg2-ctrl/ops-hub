from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class JobCostingUtility(BaseModule):

    module_info = ModuleInfo(
        module_id="job_costing",
        name="Job Costing",
        description="Allocate payments and costs to jobs. Track real GP per job.",
        category="Finance",
        sort_order=35,
        icon="TrendingUp",
    )

    def __init__(self):
        super().__init__()

    def create_window(self, master):
        from modules.job_costing.windows import JobCostingModuleWindow
        return JobCostingModuleWindow(master)
