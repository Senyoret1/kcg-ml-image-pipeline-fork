from typing import Generic, TypeVar

T = TypeVar('T')
class SingletonBase(Generic[T]):
    '''
    Base class for creating singletons. It blocks the constructor and provides a function called "get_instance"
    for being able to get the single instance clients must use.

    This in an abstract class, so it must be subclassed. When subclassing it, the subclass must be provided, like
    this: ChildClass(SingletonBase[ChildClass]). This allows this class to know what the type of the subclass is.

    Also, when subclassing this class, you must override the "_create_instance" method, to return an instance
    of the new subsclass, like this:

    def _create_instance(cls):
        return ChildClass()
    '''
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
    def _create_instance(cls) -> T:
        '''
        This function must return an instance of the subclass inherithing from this class. The instance returned
        by this function is the one that the get_instance() method will return.
        '''
        raise NotImplementedError("Abstract constructor not implemented in child!")
