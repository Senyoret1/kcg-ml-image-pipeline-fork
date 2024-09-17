# Adding code for a new collection

For adding a new collection, you must add a subfolder for the collection inside the
[“orchestration/api/api_controllers”](../api_controllers/) folder and add the 4 basic files mentioned in the code overview.
For example, if we want to create a new collection for great images, the folder should be something like
“orchestration/api/api_controllers/great_images”. You must only create the folder if it does not exists already.

Each file has a very specific content, so it is better to examine each one individually. To make this clearer, in the
[“example”](./example/) folder (inside this folder) there is code for a fictitious collection called “example”. That folder
includes the 4 basic files, with example values, including several possible escenarios and plenty of comments.

## The collection schemas file:

The file is [“example/example_db_schemas.py”](./example/example_db_schemas.py).

It includes a class with the schema all the entries in the collection must follow, called “FullDatabaseSchema”. The way to
declare the properties in the class is special, because all of them must use "Annotated" for declaring the datatype and
additional info required for MongoDB. If you want more information about what you can specify in the "Anotated" block, you
can search for "pydantic json schemas", to see how Pydantic creates json schemas with those anotations. Also, you can
search for "mongodb schema validation" to see which specific properties MongoDB uses for validations.

If you want to know how the class is converted to the schema MongoDB finally uses for internal validations, you can check
the "__process_validation_schema" function inside the "DatabaseCollectionControllerBase" class. The function has various
comments indicating how the conversion is done and you can check each step by adding code for printing to the console.

Also, this file is suposed to include classes that will be used as params for the functions that manipulate the collection.
In the example file there is a class called "AddDataSchema", which is what the function for adding entries to the example
collection receives.

## The collection management file:

The file is [“example/example_db_controller.py”](./example/example_db_controller.py).

This file has a main class, which is a child of “DatabaseCollectionControllerBase” and must include some mandatory
functions for configuring the collection and managing the responses. Also, the class includes all the functions for working
with the collection.

Note that all the functions for working with the collection return the data wrapped inside a “DatabaseOperationResponse”
instance. This is needed for returning data and errors to the callers in a consistent way.

## The API file :

The file is [“example/api_example.py”](./example/api_example.py).

This file includes all the endpoints for working with the collection.

## The API schemas file:

The file is [“example/example_api_schemas.py”](./example/example_api_schemas.py).

This file is just a collection of classes with the properties that must be recived by some endpoints and the data that is
returned by some endpoints. Note that the classes for data that is received have names that end with “Request” and the
names of the classes for responses end with “Response”.
