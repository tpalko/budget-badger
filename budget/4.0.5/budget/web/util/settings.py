from datetime import datetime 
from web.models import Settings 

class SettingsManager(object):

    def _convert(self, setting):
        if Settings.SETTINGS_TYPES[setting.name] == 'fromto':
            fromto = setting.value.split(':')
            from_val = datetime.strptime(fromto[0], "%Y-%m-%d")
            to_val = datetime.strptime(fromto[1], "%Y-%m-%d")
            return from_val, to_val 
        
        return setting.value

    def _unconvert(self, setting_name, value):
        if Settings.SETTINGS_TYPES[setting_name] == 'fromto':
            return ":".join([ datetime.strftime(v, "%Y-%m-%d") for v in value ])
        return value 

    def get(self, setting_name):
        setting = Settings.objects.filter(name=setting_name).first()        
        return self._convert(setting) if setting else setting 

    def put(self, setting_name, value):
        current_setting = self.get(setting_name)
        unconverted_value = self._unconvert(setting_name, value)
        if current_setting:
            current_setting.value = unconverted_value 
            current_setting.save()
        else:
            current_setting = Settings.objects.create(name=setting_name, value=unconverted_value)
        