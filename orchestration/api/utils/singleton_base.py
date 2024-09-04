from typing import Generic, TypeVar

T = TypeVar('T')
class SingletonBase(Generic[T]):
    __instance: T = None
    _creation_key = object()

    def __init__(self, creation_key):
        if creation_key != self._creation_key:
            raise Exception("Incorrect key for creating a instance! Use the singleton instance.")

    @classmethod
    def get_instance(cls) -> T:
        if cls.__instance == None:
            cls.__instance = cls._create_instance()
        return cls.__instance
    
    @classmethod
    def _create_instance(cls):
        raise NotImplementedError("Abstract constructor not implemented in child!")
