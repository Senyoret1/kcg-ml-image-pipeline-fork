from abc import abstractmethod
from typing import Generic, List, TypeVar
from pymongo.collection import Collection
from pymongo.database import Database
from orchestration.api.utils.singleton_base import SingletonBase

T = TypeVar('T')
class DatabaseCollectionControlletBase(SingletonBase[T], Generic[T]):
    __collection_name: str = None
    @property
    def collection_name(self) -> str:
        return self.__collection_name

    __collection: Collection = None
    @property
    def collection(self) -> Collection:
        return self.__collection
    
    __properties_sort_dict: dict = None

    def _internal_preparation(self, mongodb_db: Database, collection_name: str):
        if self.collection != None:
            raise Exception("The all images collection has already been prepared")
        
        self.__collection_name = collection_name

        if collection_name not in mongodb_db.list_collection_names():
            mongodb_db.create_collection(collection_name)
            print(f"Collection '{collection_name}' created.")
        else:
            print(f"Collection '{collection_name}' already exists.")
        
        self.__collection = mongodb_db[self.collection_name]

    def create_index_if_not_exists(self, index_key, index_name: str):
        existing_indexes = self.collection.index_information()
        
        if index_name not in existing_indexes:
            self.collection.create_index(index_key, name=index_name)
            print(f"Index '{index_name}' created on collection '{self.collection.name}'.")
        else:
            print(f"Index '{index_name}' already exists on collection '{self.collection.name}'.")
    
    @abstractmethod
    def _perform_db_element_processing(self, data: dict):
        raise NotImplementedError("Abstract function not implemented in child!")

    def _process_data_types(self, data):
        if data is None:
            pass
        elif isinstance(data, dict):
            self._perform_db_element_processing(data)
            self.__sort_dict_properties(data)
        elif isinstance(data, List):
            for image_data in data:
                self._perform_db_element_processing(image_data)
                self.__sort_dict_properties(image_data)
        else:
            raise Exception("It is not possible to process the data types of an unknown object")
        
    def __sort_dict_properties(self, dict_to_process: dict):
        if self.__properties_sort_dict == None:
            return

        keys = list(dict_to_process.keys())
        keys.sort(key=self._get_property_sort_value)

        new_dict = {}
        for key in keys:
            new_dict[key] = dict_to_process[key]
        
        dict_to_process.clear()
        for key in keys:
            dict_to_process[key] = new_dict[key]
        #return new_dict

    def _get_property_sort_value(self, property_name: str):
        property_value = self.__properties_sort_dict.get(property_name)
        if property_value == None:
            return 0
        
        return property_value
    
    def _set_top_properties(self, properties_list: List[str]):
        if not properties_list:
            self.__properties_sort_dict = None
            return
        
        self.__properties_sort_dict = {}
        for i, property in enumerate(properties_list):
            self.__properties_sort_dict[property] = (len(properties_list) - i) * -1
