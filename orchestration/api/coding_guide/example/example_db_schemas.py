from __future__ import annotations
from typing import Optional
from typing_extensions import Annotated

from pydantic import BaseModel, ConfigDict, Field

class ExampleDbSchemas():
    '''
    All schemas are inside a class called f"{collection_name}DbSchemas". This is for code organization.
    '''

    class DatabaseSchema(BaseModel):
        '''
        This is the database schema class. It includes all the fields that will be part of the collection.
        What is declared in this class will be used by MongoDB to validate all the new entries added to the
        collection and also when trying to update old entries. Note that the class is a subclass of BaseModel,
        so it uses Pydantic validation. Also note that the "_id" property MongoDB automatically adds is not in
        this class.
        '''

        model_config = ConfigDict(extra='forbid')
        '''
        This tells the validator that only the properties specified in this class are considered valid.
        If anyone tries to save in the collection a property that is not here, MongoDB will reject the operation.
        This is an attibute provided by Pydantic and is ignored for MongoDB validation, which means that MongoDB
        will not expect a property called "model_config" in each entry in the collection.
        '''

        index: Annotated[
            int,
            Field(
                json_schema_extra={'bsonType': 'int'}
            )
        ]
        '''
        This is the first real field of the class. The first thing to take into account is that the datatype
        must be defined, and it must be inside "Annotated". After the Python datatype, the following 3
        lines indicate which datatype MongoDB must use to save the data internally. Take into account that
        Python and MongoDB types are similar but different, so a clear MongoDB datatype is needed in all
        the class properties, to ensure that MongoDB works in a predictable way. You can search for
        "bson types" in a search engine to see the updated list of types MongoDB accepts.
        '''

        name: Annotated[
            str,
            Field(
                json_schema_extra={'bsonType': 'string'},
                min_length=32,
                max_length=128,
            )
        ]
        '''
        This is very similar to the previous property, but it is a string. See how the Python datatype has a different
        name than the MongoDB datatype. Also, there are 2 new preperties: "min_length" and "max_length". Those are
        validators that indicate that the name must be have 32 characters (inclusive) or more and also 128 characters
        (inclusive) or less. Those are standard Pydantic validators, so you can find information about what validators
        can be used for each datatype in the Pydantic documentation.
        '''

        uuid: Annotated[
            str,
            Field(
                description='Uuids are saved as longs internally.',
                json_schema_extra={'bsonType': 'long'}
            )
        ]
        '''
        This is an UUID, which is a special case. Note that the Python datatype is "str" but the MongoDB datatype is
        "long". Those two are incompatible datatypes, because one is a string and the other is a number. This is because
        in the API and the Python code we are suposed to work with UUIDs using the string representation, which is something
        like "1234-5678-90AB-CDEF", because that prevents several problems with interoperability. That is all the Python code
        must know: UUIDs are strings, to make things simple.

        However, we must not save the UUIDs as strings in the database, because that would be very inefficient. For
        efficiency we must save a smaller datatype, which is a unsigned 64bit long number. That is why the MongoDB datatype
        is different. We work with strings in Python, but for data storage MongoDB will expect longs.
        
        The problem here is that if we try to save the string UUID to MongoDB, the conversion will not be made automatically,
        the operation will fail because MongoDB is expecting a long. Also, all database queries will return longs, not
        strings. To solve this, the class for managing the collection will have to take care of the data conversion just before
        saving it to the database and right after getting data from it. That class has some helpers for that, so if you need
        more information, just see the help related to that class.
        '''

        optional_value: Annotated[
            Optional[str],
            Field(
                json_schema_extra={'bsonType': 'string'}
            )
        ] = None
        '''
        This is an optional property, but you must take some care with it. The Optional[str] part and the default "None" value
        will tell Pydantic that this property can be ignored. If you want to save a new entry in Mongodb, and the new entry
        does not include this property at all, it will work, there is no problem with that. However, you should take care with
        your Python code, because if what you try to save in MongoDB is an intance of this class, the data sent to MongoDB may
        include "optional_value" set to "None" by default (because the property has a None value set by default in the
        declaration) and the operation will fail. This is because the "bsonType" property is telling MongoDB that if the property
        exists, it must be a string, and None is not a string. In summary, take into account that for MongoDB this means that you
        are allowed to not include the property, but that does not mean that you are allowed to send "None".

        Also, take into account that the property may not be present in the query responses. MongoDB will not return None as
        default when the property is not in the returned entry, the property will simply not be there.
        '''

        nullable_value: Annotated[
            Optional[str],
            Field(
                json_schema_extra={"oneOf": [
                    {
                    "bsonType": 'string'
                    },
                    {
                    "bsonType": 'null'
                    }
                ]}
            )
        ]
        '''
        This is different from the previous example. This property is not optional. As the property does not have a default value,
        Pydantic will mark it as mandatory. When declaring the Python datatype, the "Optional" part is only indicating that
        it can be a string or None, not that it can be removed. When declaring the MongoDB dataype, we need to indicate that
        it can be a string or null, both datatypes are valid. For this, a "oneOf" property is used, which allows to specific
        more than one aceptable datatype. In this case we are telling MongoDB that this property must contain a valid string
        or null (which is how the None datatype from Python is saved in MongoDB).

        This same way of declaring the aceptable datatypes can be used for other cases, not just allowing null. For example,
        you can declare that a property can accept a string or an int, if there is a case in which that makes sense.
        '''

    class FullDatabaseSchema(DatabaseSchema):
        '''
        The previous class defined all the relevant properties for the elements that will be saved in the collection. However,
        it did not included the "_id" field MongoDB automatically adds. That field is important for the internal validation
        MongoDB makes, but is annoying for working in Python, because that is a field that is only specific to MongoDB and
        we should ignore it as much as possible to maintain the separation of concerns. If we use the "_id" field freely
        outside the classes made specifically for working with MongoDB, in the future it will be much more difficult to
        use another data storage technology if needed. Because of that, we create another class just for adding that property.
        '''

        id: Annotated[
            str,
            Field(
                validation_alias="_id",
                json_schema_extra={'bsonType': 'objectId'}
            )
        ]
        '''
        Note that the property cannot be called "_id" in the Python code or Pydantic will ignore it. Because of that, we just
        call it "id", but add a "validation_alias" property on the anotation indicating how the field is called in MongoDB. The
        "validation_alias" property is provided by Pydantic for this kind of cases.
        '''


    class AddDataSchema(BaseModel):
        '''
        This is a simple class is a simple example that is used as the param for the function that adds entries to the
        collection. It does not have anything special, but it is good to define classes with Pydantic validation for the params
        that will be received by functions that work with the collection. This helps to avoid sending crazy data to those
        functions and makes the autocompletion tools of the IDE work.
        '''
        name: str
