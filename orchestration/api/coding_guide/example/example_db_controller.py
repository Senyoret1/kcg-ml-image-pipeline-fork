from __future__ import annotations

from pydantic import validate_call
import pymongo.collection
from pymongo.collection import Collection
from pymongo.database import Database
import pymongo
import pymongo.database

from orchestration.api.api_controllers.all_images.all_images_db_schemas import AllImagesDbSchemas
from orchestration.api.api_controllers.database_collection_controller_base import DatabaseCollectionControllerBase
from orchestration.api.manual.example.example_db_schemas import ExampleDbSchemas
from orchestration.api.utils.database_operation_response import DatabaseOperationResponse, DatabaseOperationResponseType
from orchestration.api.utils.uuid64 import Uuid64

class ExampleDbController(DatabaseCollectionControllerBase['ExampleDbController']):
    '''
    This is an example class for managing a collection called "example". All classes like this must be subclasses of
    "DatabaseCollectionControllerBase", which provides various helpers for working with collections. Note that for
    extending "DatabaseCollectionControllerBase" you must do it sending the current class inside "[]". For this to work
    you must add "from __future__ import annotations" at the top of the file.

    By extending "DatabaseCollectionControllerBase" the constructor for this class will be blocked and the class
    will work as a singleton. You must use "ExampleDbController.get_instance()" to access the instance of this class.
    '''

    @classmethod
    def _create_instance(cls):
        '''
        The "_create_instance" function is overrided from the base "DatabaseCollectionControllerBase" class. The only
        thing this function must do is create an instance of this class and return it. This is needed for the automatic
        singleton functionality to work.
        '''
        return ExampleDbController(cls._creation_key)
    
    def prepare(self, mongodb_db: Database) -> Collection:
        '''
        This function takes care of making all the initiallizations needed for working with the collection. It returns
        the collection, in case the code that called this function needs it.
        '''

        '''
        When creating a function like this, the first step must always be a call to "self._internal_preparation()". The
        "_internal_preparation" function is defined in "DatabaseCollectionControllerBase", the super class of this
        subclass.

        That function takes care of creating the collection if it does not exist and sets up the schema validation.
        The third param is the "FullDatabaseSchema" class created in the schemas file, which will be used for validation
        by MongoDB. Take into account that "FullDatabaseSchema" is the class that includes the "_id" param.

        You can check the function documentation and code for more information.
        '''
        self._internal_preparation(mongodb_db, "all-images", AllImagesDbSchemas.FullDatabaseSchema)

        '''
        This function is for setting which properties must be at the top in the responses returned by this class. In this
        example, the "uuid" property will be returned first, the "name" property will be returned second and all the
        other properties will be returned after that, in an undefined order.
        '''
        self._set_top_properties(['uuid', 'name'])

        '''This adds an unique index to the uuid property. Check the function documentation for more info.'''
        self.create_index_if_not_exists(
            [('uuid', pymongo.ASCENDING)],
            'example_unique_uuid_index'
        )

        return self.collection
    
    @validate_call
    def add_value(self, data: ExampleDbSchemas.AddDataSchema) -> DatabaseOperationResponse[AllImagesDbSchemas.DatabaseSchema]:
        '''
        This is an example function for saving data in MongoDB. It was not declared in the superclass or other place, just here.
        When creating a class for managing a collection you are suposed to create various functions like this, for creating,
        getting, updating and deleting elements.

        In functions like this, the response must always be an instance of "DatabaseOperationResponse". This allows not just to
        return the responses from the database, but also to inform about any error. When hinting that this function returns an
        instance of "DatabaseOperationResponse", you must put inside "[]" the type that the function is expected to return when
        the operation finishes correctly. For example, this function is suposed to return a instance of
        "AllImagesDbSchemas.DatabaseSchema".

        Note that the function is decorated with "@validate_call". This is important to avoid allowing invalid data to be sent
        to this function. That decorator will make Pydantic validate all the params sent to the function.
        '''

        '''Use "try", to catch unexpected errors. This allow to append to the error description that the error was in this
        part of the code.'''
        try:
            '''
            All validations for mainatining data consistency must be done here, not in the API code. For example, here we define
            that the database must not have any entry with "invalid" as the name.
            '''
            if data.name == "invalid":
                '''If the validation fails, return an error response like this. It includes the error cause and a description,
                so that any code calling this function can know what went wrong and inform any final user.'''
                return DatabaseOperationResponse(
                    response_type=DatabaseOperationResponseType.REQUEST_REJECTED,
                    error_description="The name must not be 'invalid'."
                )
            
            '''Get a dictionary before adding the data to the database.'''
            new_document = data.model_dump()
            
            ''' *** Make any other additional operation. Note that the collection expects additial preperties, not just the name. *** '''
            
            '''Insert the data to the database'''
            self.collection.insert_one(new_document)

            '''
            This processes the response to ensure that the properties have the correct datatype and no unneded properties
            are returned (like the "_id" property MongoDB automatically adds). This is a helper method provided by the
            DatabaseCollectionControllerBase base class, that can clean single dict instances and also lists of dicts, but it
            is not a magic obscure method. The actual procedure for cleaning each entry is in the "_perform_db_element_processing"
            function at the end of this file.
            '''
            self._process_data_types(new_document)

            '''Return the response wrapped in the standard database operation response object. Always return database
            operations in a DatabaseOperationResponse object.'''
            return DatabaseOperationResponse(response_content=new_document)
        except Exception as e:
            '''Here we append text to the original error description, to know that the issue heppened while excecuting this function.'''
            raise Exception(f"Error adding an entry to the example collection: {e}")

    def list_all_entries(self) -> DatabaseOperationResponse[list[AllImagesDbSchemas.DatabaseSchema]]:
        '''
        This is just a simple example of a function for returning all the entries in the collection. It is similar to the
        previous function.
        '''

        try:
            '''This code just gets all the entries and puts them in a list.'''
            cursor = self.collection.find({}).sort('name', 1)
            data = list(cursor)

            '''
            We clean all the results returned by the query. In this case, this will remove the "_id" property from all the
            entries and convert all the UUIDs from the number saved in MongoDB to the string representation that is suposed to
            be used in all other parts of the code. Remember that the numeric representation is just an implementation detail
            for saving in MongoDB, not something that the rest of the code should care about.

            Almost all the functions that return database data must call this function before returning the data, to ensure that
            all the problematic values are converted or removed, as appropriate.
            
            If you want to see how the convertion is done, check the "_perform_db_element_processing" function at the end of
            this file.
            '''
            self._process_data_types(data)

            '''The cleaned entries are returned, always in a standard database operation response object.'''
            return DatabaseOperationResponse(response_content=data)
        except Exception as e:
            raise Exception(f"Error while getting a elements list from the example collection: {e}")
    
    def delete_entry_by_uuid(self, element_uuid: str) -> DatabaseOperationResponse[int]:
        '''
        This is an example of a function for removing an entry from the collection. An important thing to take into account
        is that the function returns a number. This is an important convention for our codebase: all functions for deleting
        data from the database return how many entries were deleted during the operation. It does not mater if the function
        is for removing one or more entries, it must return how many entries were trully removed by the databse engine. This
        allows helpers functions create automatic responses indicating if the data was found, how many entries were
        really removed, etc.
        '''

        try:
            '''
            Remember that all Python code works with UUIDs as strings, not numbers, but we save the UUIDs as number in MongoDB.
            This is an internal implementation detail that nobody outside the MongoDB code should really care about. Because of
            this, the function receives the UUID as a string and we have to convert it to a number here before making a
            database query.
            '''
            numeric_uuid = Uuid64.from_formatted_string(element_uuid).to_mongo_value()

            '''We make the operation and return how many elements were removed.'''
            result = self.collection.delete_one({"uuid": numeric_uuid})
            return DatabaseOperationResponse(response_content=result.deleted_count)
        except Exception as e:
            raise Exception(f"Error while deleting an entry the {element_uuid} uuid in database: {e}")

    def _perform_db_element_processing(self, data: dict):
        '''
        This function is very important. It is defined in the DatabaseCollectionControllerBase parent class and must always be
        present in childs of that class. This function is the one that cleans the database responses.

        For creating this function you must first know which elements are saved in the database in a datatype that is different
        from the one used in the Python code, which preperties are not relevant outside this class and other internal details.

        For example, if you check the schema for the example collection we are pretending to manage in this class, you will see
        2 important things:

        1) MongoDB always adds a "_id" property to the database entries. That property is only relevant to MongoDB, it does not
        exists if we change the database technology, so returning it will only make things confusing to the rest of the code,
        specially if we change the database engine in the future, so it has to be removed.

        2) The collection has an UUID field that is saved in MongoDB as a uint64 number, but the Python code works with the UUIDs
        as strings. This means that everytime that we get an entry from MongoDB we will get a number in the uuid property and we
        must convert that to the correct string value before returning the entry.

        This function addresses both issues. 

        Note: this is the function that is called internally every thime you call "self._process_data_types()" in this class.
        '''

        '''This addresses the first issue. The "_id" property is removed, if it exists.'''
        data.pop('_id', None)

        '''
        This addresses the second issue. If there is an uuid property, the code checks the datatype of the value and tries to
        convert it to the correct string format.
        
        Something very important to take into account is how this code does not assume that the preperty exists or its format,
        it checks that. This allows the function to be usable in special cases. For example, we could create a new function that
        returns only a few properties, excluding the uuid. If this function assumes that the uuid field is always present and is
        always a number, it would not be able to clean the entries retrieved by that function, because there would be a runtime
        exception trying to access data that does not exists.
        '''
        if "uuid" in data:
            if isinstance(data['uuid'], int):
                uuid64 = Uuid64.from_mongo_value(data['uuid'])
                data['uuid'] = uuid64.to_formatted_str()
            if isinstance(data['uuid'], Uuid64):
                data['uuid'] = data['uuid'].to_formatted_str()
