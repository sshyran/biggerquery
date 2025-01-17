import os

from .interactive import InteractiveDatasetManager


class EnvConfig:
    def __init__(self,
                 name: str,
                 properties: dict):
        self.name = name
        self.properties = properties


class Config:
    def __init__(self,
                 name: str,
                 properties: dict,
                 is_master: bool = True,
                 environment_variables_prefix: str = ''):
        if is_master:
            self.master_config_name = name

        self.configs = {
            name: EnvConfig(name, properties)
        }

        self.environment_variables_prefix = environment_variables_prefix

    def resolve_property(self, property_name: str, config_name: str):
        return self.resolve(config_name)[property_name]

    def resolve(self, name: str = None) -> dict:
        env_config = self._get_env_config(name)

        properties_with_placeholders = {key: self._resolve_property_with_os_env_fallback(key, value)
                for (key, value) in env_config.properties.items()}

        string_properties = {k: v for (k, v) in properties_with_placeholders.items() if isinstance(v,str)}

        return {key: self._resolve_placeholders(value, string_properties)
                for (key, value) in properties_with_placeholders.items()}


    def add_configuration(self, name: str, properties: dict):

        all_properties = self._get_master_properties()
        all_properties.update(properties)

        self.configs[name] = EnvConfig(name, all_properties)

        return self

    def _get_master_properties(self) -> dict:
        if not self._has_master_config():
            return {}

        return self._get_env_config(self.master_config_name).properties.copy()

    def _has_master_config(self) -> bool :
        return hasattr(self, 'master_config_name')

    def _resolve_default_config_name(self):
        return self._resolve_property_from_os_env('env')

    def _get_env_config(self, name: str) -> EnvConfig:

        used_name = name or self._resolve_default_config_name()

        if used_name not in self.configs:
            raise ValueError('no such config name: ' + used_name)

        return self.configs[used_name]

    def _resolve_property_with_os_env_fallback(self, key, value):
        if value is None:
            return self._resolve_property_from_os_env(key)
        else:
            return value

    def _resolve_property_from_os_env(self, key):
        env_var_name = self.environment_variables_prefix + key
        if env_var_name not in os.environ:
            raise ValueError(
                "failed to load property value '" + key + "' from os.environment, no such env variable '" + env_var_name + "'")
        return os.environ[env_var_name]

    def _resolve_placeholders(self, value, variables:dict):
        if isinstance(value, str):
            modified_value = value
            for k, v in variables.items():
                if v != value:
                    modified_value = modified_value.replace('{' + k + '}', v)
            return modified_value
        else:
            return value


class DatasetConfig:
    def __init__(self,
                 env: str,
                 project_id: str,
                 dataset_name: str = 'None',
                 internal_tables: list = None,
                 external_tables: dict = None,
                 properties: dict = None,
                 is_master: bool = True):
       all_properties = (properties or {}).copy()
       all_properties['project_id'] = project_id
       all_properties['env'] = env # for placeholders resolving
       all_properties['dataset_name'] = dataset_name
       all_properties['internal_tables'] = internal_tables or []
       all_properties['external_tables'] = external_tables or {}

       self.delegate = Config(name=env, properties=all_properties, is_master=is_master)

    def add_configuration(self,
                          env: str,
                          project_id: str,
                          dataset_name: str = None,
                          internal_tables: list = None,
                          external_tables: dict = None,
                          properties: dict = None):

        all_properties = (properties or {}).copy()

        all_properties['project_id'] = project_id
        all_properties['env'] = env  # for placeholders resolving

        if dataset_name:
            all_properties['dataset_name'] = dataset_name

        if internal_tables:
            all_properties['internal_tables'] = internal_tables

        if external_tables:
            all_properties['external_tables'] = external_tables

        self.delegate.add_configuration(env, all_properties)
        return self

    def create_dataset_manager(self, env: str = None) -> InteractiveDatasetManager:
        return InteractiveDatasetManager(
            project_id=self.resolve_project_id(env),
            dataset_name=self.resolve_dataset_name(env),
            internal_tables=self.resolve_internal_tables(env),
            external_tables=self.resolve_external_tables(env),
            extras=self.resolve_extra_properties(env))

    def resolve_extra_properties(self, env: str = None):
        return {k: v for (k, v) in self.resolve(env).items() if self._is_extra_property(k)}

    def resolve(self, env: str = None) -> dict :
        return self.delegate.resolve(env)

    def resolve_property(self, property_name: str, env: str = None):
        return self.delegate.resolve_property(property_name, env)

    def resolve_project_id(self, env: str = None) -> str:
        return self.resolve_property('project_id', env)

    def resolve_dataset_name(self, env: str = None) -> str:
        return self.resolve_property('dataset_name', env)

    def resolve_internal_tables(self, env: str = None) -> str:
        return self.resolve_property('internal_tables', env)

    def resolve_external_tables(self, env: str = None) -> str:
        return self.resolve_property('external_tables', env)

    def _is_extra_property(self, property_name) -> bool:
        return property_name not in ['project_id','dataset_name','internal_tables','external_tables', 'env']

