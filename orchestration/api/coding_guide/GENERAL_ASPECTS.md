# General aspects

The orchestation code is mainly for 2 things: managing the database collections and managing the API endpoints for being able
to work with the data in those collections. This means that the code is divided mainly in collections, so there is specific
independent code for managing things like “generated images”, “image datasets”, “users”, etc.

This document has an overview about what the code does and how it is organized. Each part of the code is documented in more
detail in other files.

## Technologies:

- The orchestation code works using the Python laguaje.

- The API code works using FastAPI. You can see the version being used by checking the requeriment files in the root of
the repository.

- The database code works using MongoDB, with Pymongo as the database driver.

- Pydantic is used for performing validations in several classes and functions.

For better underestanding this documentation, it is recommended to have at least a basic underestanding about how to use
those technologies.

## Code organization:

As said before, the code is separated in “sections”. Those sections are basically subfolders with code for working with
one specific database collection, so we have a subfolder with the code for image datasets, another one for external images,
etc. Those subfolders are inside the [“orchestration/api/api_controllers”](../api_controllers/) folder.

Inside each one of those subfolders there at least 4 files:

- <ins>A file with a class for managing the collection:</ins> it includes code for creating the collection, managing the
indexes and making the data operations (add data, get data, etc.). The class includes functions for allowing other parts of the
code to access/manipulate the data in the collection. The idea is that the data of the collection should only be accesed and
manipulated by using the functions provided by the class. The file is normally called f"{collection_name}_db_controller".

- <ins>A file with database schema classes:</ins> it includes a main class with the properties that the entries in the
collection may/must have. It also may include helper classes with the data that must be received/returned by the functions
in class mentioned in the previous point. The file is normally called f"{collection_name}_db_schemas".

- <ins>A file with the API endpoints:</ins> it includes all the endpoints that allow to work with the collection. The file
is normally called f"api_{collection_name}".

- <ins>A file with the API schemas:</ins> it includes classes with all the objects the API endpoints receive/return. The
file is normally called f"{collection_name}_api_schemas".

## Basic principles:

One of the basic principles followed in the code is the separation of concerns. Each file must take care of a specific part
of the functionality. In this code base that means:

- The class for managing the database collection should only have code for managing the collection, without any API code.
If there are validations that must be done to maintain the data consistency in the database, those validations must be done
in the class that manages the collection, not in the API code. For example, if we must not allow the removal of any image
dataset which already has images assined to it, that validation must be done in the class that manages the datasets
collection, in the function that deletes the datasets, not in the API code.

- The class for the API endpoints should not access the database collections directly. For making any operation, it must
use the functions provided by the collection management classes. Also, the class must make all the validations it needs to
ensure that no invalid data is sent in the API requests, but the final responsability to avoid entering invalidad data in
the database is in the collection management class, not the API class. The validations in the API class are good for
returning good error messages in case of problems, instead of ensuring data integrity.

One of the main objectives of this is to be as database agnostic as possible, so if we migrate to another database engine,
it can be done with the least amount of problems possible.