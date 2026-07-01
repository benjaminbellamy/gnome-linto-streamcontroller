# Import StreamController modules
from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.PluginManager.ActionHolder import ActionHolder
from src.backend.PluginManager.ActionInputSupport import ActionInputSupport
from src.backend.DeckManagement.InputIdentifier import Input

# Import actions
from .actions.LintoToggle.LintoToggle import LintoToggle


class LinTOPlugin(PluginBase):
    def __init__(self):
        super().__init__()

        self.toggle_holder = ActionHolder(
            plugin_base=self,
            action_base=LintoToggle,
            action_id="ai_linto_gnomelinto::Toggle",
            action_name="LinTO Toggle",
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNTESTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            },
        )
        self.add_action_holder(self.toggle_holder)

        self.register(
            plugin_name="LinTO",
            github_repo="https://github.com/benjaminbellamy/gnome-linto-streamcontroller",
            plugin_version="0.1.0",
            app_version="1.5.0-beta.14",
        )
