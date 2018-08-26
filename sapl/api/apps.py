from django import apps
from sapl.translation import ugettext_lazy as _


class AppConfig(apps.AppConfig):
    name = 'sapl.api'
    label = 'api'
    verbose_name = _('API Rest')
