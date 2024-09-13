from abc import abstractmethod
from typing import Generic, List, Optional, Type, TypeVar
from pydantic import BaseModel
from pymongo.collection import Collection
from pymongo.database import Database
from orchestration.api.utils.singleton_base import SingletonBase

T = TypeVar('T')
class DatabaseCollectionControllerBase(SingletonBase[T], Generic[T]):
    '''
    Base class for the database collections. All classes for managing a specific collection must inherit from it.

    This in an abstract class, so it must be subclassed. When subclassing it, the subclass must be provided, like this:
    ChildClass(DatabaseCollectionControllerBase[ChildClass]). This allows this class to know what the type of the subclass is.
    Also, this class inherits from SingletonBase, so the abstract functions for that class must be implemented too.

    All subsclasses must call the "_internal_preparation" function before making their own preparations and
    override the "_process_data_types" function.
    '''

    __collection_name: str = None
    @property
    def collection_name(self) -> str:
        '''Name of the collection this class is managing.'''
        return self.__collection_name

    __collection: Collection = None
    @property
    def collection(self) -> Collection:
        '''The collection this class is managing.'''
        return self.__collection
    
    __properties_sort_dict: dict = None
    '''Dict with the properties that must be put at the top when returning values from the collection.'''

    _validation_schema: dict = None
    '''Schema used for validating the collection values in MongoDB. For more information about the format that this schema must
    have, check the documentation about database development for this project.'''

    def _internal_preparation(self, mongodb_db: Database, collection_name: str, schema_class: Optional[Type[BaseModel]]):
        '''
        This function must be called one time by all subclases, before making any initial preparation.
        It creates the collection if it does not exists, configures the schema validation and performs other
        preparations needed internally.
        
        Args:
            mongodb_db (Database): MongoBD database instance.

            collection_name (str): Name of the collection this class will manage. If the collection does not exists, it is created.

            schema_class (Type[BaseModel]): Schema that MongoDB will use to validate the entries added to the collection. For more information about the format that this schema must have, check the documentation about database development for this project. If not set, no schema validation will be performed.
        '''
        if self.collection != None:
            raise Exception("The collection has already been prepared")
        
        self.__collection_name = collection_name

        if collection_name not in mongodb_db.list_collection_names():
            mongodb_db.create_collection(collection_name)
            print(f"Collection '{collection_name}' created.")
        else:
            print(f"Collection '{collection_name}' already exists.")
        
        self.__collection = mongodb_db[self.collection_name]

        self.__process_validation_schema(schema_class)

        if self._validation_schema:
            # Only modify the validation schema if it was changed.
            if self.__collection.options().get("validator") != self._validation_schema:
                mongodb_db.command("collMod", self.collection_name, validator=self._validation_schema)
    
    def __process_validation_schema(self, schema_class: Optional[Type[BaseModel]]):
        '''Converts the schema validation class to the format required by MongoDB, for performing the validations internally.
        The schema in the format required by MongoDB is saved in the "_validation_schema" property, on this class.'''

        if schema_class != None:
            # Create the json schema using pydantic.
            self._validation_schema = schema_class.model_json_schema()

            properties: dict = self._validation_schema.get('properties', {})
            if properties == None:
                # This is an unexpected error.
                raise Exception(f"Imposible to create the validation schema for the {self.collection_name} collection.")
            
            # Remove unneded properties added by pydantic.
            self._validation_schema.pop("title")
            self._validation_schema.pop("type")
            # Required by MongoDB.
            self._validation_schema["bsonType"] = "object"
            
            key: str
            for key in properties:
                p: dict = properties[key]
                # If the bsonType property was not added to a property, it is not possible to create a valid schema.
                if p.get("bsonType", None) == None:
                    raise Exception(f"Imposible to create the validation schema for the {self.collection_name} collection. You must define a 'bsonType' value for the '{p}' property.")
                
                # If the title property is just the key name, remove it.
                title: str = p.get("title", None)
                if title and title.upper() == key.replace('_', ' ').upper():
                    p.pop("title")
                
                # This is for json schemas, not for bson schemas, so it is removed.
                p.pop("type")

            # Save the full schema.
            self._validation_schema = {"$jsonSchema": self._validation_schema}

    def create_index_if_not_exists(self, index_key, index_name: str, unique_index=False):
        '''
        Adds an index to the collection, if it does not exist. For knowing if an index exits, the name is used, so if
        the contents of the index are changed but the name is the same, nothing will happen.

        Args:
            index_key: The contents of the index. It is the same that would be sent to the "collection.create_index()" function pymongo provides.
            index_name: Index name, used to identify the index and knowing if it already exists.
            unique_index: If true, the index is created as an unique index, which does not allow duplicated values.
        '''
        existing_indexes = self.collection.index_information()
        
        if index_name not in existing_indexes:
            self.collection.create_index(index_key, name=index_name, unique=unique_index)
            print(f"Index '{index_name}' created on collection '{self.collection.name}'.")
        else:
            print(f"Index '{index_name}' already exists on collection '{self.collection.name}'.")
    
    @abstractmethod
    def _perform_db_element_processing(self, data: dict):
        '''
        Processes an element returned from the database, to remove all the unneded values and convert the datatypes as needed.

        Args:
            data (dict): single entry obtained from the database.
        '''
        raise NotImplementedError("Abstract function not implemented in child!")

    def _process_data_types(self, data: dict | List[dict] | None):
        '''
        Processes one or more elements returned from the database, to remove all the unneded values and convert the datatypes as needed.
        It will also sort the properties, if properties were configured in this class to be shown at the top.

        Args:
            data: Must be a dict, with the data of a single database entry, or a list of dicts, with several elements obtained from the database. If the value is a list, all the elements will be processed.
        '''
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
            raise Exception("It is not possible to process the data types of an unknown object.")
        
    def __sort_dict_properties(self, dict_to_process: dict):
        '''Sorts the properties of a dict, using the top properties configured for this class instance.'''
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

    def _get_property_sort_value(self, property_name: str):
        property_value = self.__properties_sort_dict.get(property_name)
        if property_value == None:
            return 0
        
        return property_value
    
    def _set_top_properties(self, properties_list: List[str]):
        '''Sets which properties must be at the top when returning database elements with this class instance. The order of the
        properties in the provided list will be the order in which the properties will be returned in the responses.'''

        if not properties_list:
            self.__properties_sort_dict = None
            return
        
        self.__properties_sort_dict = {}
        for i, property in enumerate(properties_list):
            self.__properties_sort_dict[property] = (len(properties_list) - i) * -1
