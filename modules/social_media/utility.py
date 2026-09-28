from framework.base_module import BaseModule
from framework.module_info import ModuleInfo


class SocialMediaUtility(BaseModule):

    module_info = ModuleInfo(
        module_id="social_media",
        name="Social Media",
        description="Build branded posters from your own job photos, save them by month and post them.",
        category="Tools",
        sort_order=92,
        icon="Share",
    )

    def __init__(self):
        super().__init__()

    def create_window(self, master):
        from modules.social_media.windows import SocialMediaModuleWindow
        return SocialMediaModuleWindow(master)
