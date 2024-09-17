from fastapi import Request, APIRouter, Query
from orchestration.api.manual.example.example_api_schemas import ExampleApiSchemas
from orchestration.api.manual.example.example_db_controller import ExampleDbController
from orchestration.api.manual.example.example_db_schemas import ExampleDbSchemas
from orchestration.api.utils.api_operations_utils import ApiUtils
from ...api_utils import StandardSuccessResponseV1, ApiResponseHandlerV1, WasPresentResponse

router = APIRouter()

@router.post("/examples/add-example",
          description="Adds a new example to the examples collection.",
          tags=["examples"],
          status_code=201,
          response_model=StandardSuccessResponseV1[ExampleDbSchemas.DatabaseSchema],
          responses=ApiResponseHandlerV1.listErrors([422, 500]))
async def add_new_bucket(request: Request, example: ExampleApiSchemas.ExampleCreationRequest):
    '''
    This is an example endpoint that is suposed to add a new entry in the example collection. The declaration itself
    follows various standards, so please check the API development documentation for more info about that. Also note
    that it specifies that the endpoint must return an "ExampleDbSchemas.DatabaseSchema" instance as its main response
    content, because that is what the database operation it calls is suposed to return.

    The "example" param contains the data that must be sent in the post body. It is a Pydantic model, so any required
    validation must be set in that model, including if each field is optional or not.
    '''

    '''Construct the object expected by the function that adds the data to the collection. This prevents errors that may
    appear when using dicts by hand.'''
    data_to_save = ExampleDbSchemas.AddDataSchema(name=example.example_name)

    '''To make the opertation, use the function provided by the collection management class. Don't use the collection
    directly here.'''
    db_response = ExampleDbController.get_instance().add_value(data_to_save)

    '''All the requests in our API code have a "request.state.response_handler" property with an instance of
    "ApiResponseHandlerV1". That instance provides the "process_normal_database_response" function, which takes the standard
    database operation result instance returned by any database operation function, processes it and constructs the correct API
    response from it. That function will return a standard API error response if the operation failed, and a success response
    if the operation finished correctly.

    The second param that is sent to it is the http status code that will be returned if the operation finished correctly. That
    code is set to 200 by default, so it must be changed only if we want to return a special code, like in this cases, in which
    we return 201 because that is better when creating a new entry.
    '''
    return request.state.response_handler.process_normal_database_response(
        db_response, 201
    )

@router.get("/examples/list-all-entries",
            description="Returns all the entries in the examples collection.",
            tags=["examples"],
            response_model=StandardSuccessResponseV1[ExampleApiSchemas.EntriesListResponse],
            responses=ApiResponseHandlerV1.listErrors([422, 500]))
async def list_all_images(
    request: Request,
    max_entries: int = Query(20, description="Limit on the number of results returned.", ge=1),
    order: ApiUtils.SortOrder = Query(ApiUtils.SortOrder.desc, description="Order in which the data should be returned. 'asc' for oldest first, 'desc' for newest first.")
):
    '''
    This is a simple example endpoint for getting all the entries in the example collection. Note that it has 2 params. None
    of them is really used in the code, but are good examples to illustrate some important concepts.
    
    The first param is suposed to be a number to limit how many entries are going to be returned. The important part is that is
    has a "ge" property indicating that the number must be at least 1. This kind of validations must be done always, or at
    least when it makes sense, to inmediatelly reject invalid data. You can find the available validation functions in the
    FastAPI documentation.

    The second param is suposed to be the order in which the data will be sorted. Note that the type is an enum. That enum has
    only 2 values (you can see that by checking the code of the enum). This will cause 2 things to happen. The first one is that
    the documentation will show those 2 values as the only valid values for the param, which is very good to knowing how the
    endpoint works. The other thing is that FastAPI will automatically validate the field, so that any value not listed in that
    enum will be rejected.

    Apart from that, note that each param has a clear explanation about what does it do. A simple description like "sort order"
    does not say much and leaves questions like "what the valid values are?" and "what field is being using for sorting".
    Leaving questions like that should be avoided always.
    '''

    '''We get the data from the collection management class.'''
    db_response = ExampleDbController.get_instance().list_all_entries()

    '''
    The previous function returns the entries as a list, right away, but that is not how this endpoint is suposed to respond. If
    you see the endpoint declaration, it says that the endpoint is suposed to return a response like what is defined in the
    ExampleApiSchemas.EntriesListResponse class. The problem is that that class says that the list must be wrapped inside a property
    called "entries", so we must do exactly what the class indicates, wrap the list inside a property called "entries".
    '''
    db_response.response_content = {"entries": db_response.response_content}

    '''After the fix for the response format, we return the response using the helper function.'''
    return request.state.response_handler.process_normal_database_response(
        db_response
    )

@router.get("/examples/delete-entry-by-uuid", 
            description="Removes from the database the entry with the provided UUID.",
            tags=["examples"],
            response_model=StandardSuccessResponseV1[WasPresentResponse],
            responses=ApiResponseHandlerV1.listErrors([422, 500]))
async def get_image_by_hash(
    request: Request,
    uuid: str
):
    '''
    This is an example endpoint for removing an entry from the example collection. The first thing to note is that it is
    suposed to respond as defined in the "WasPresentResponse" class. This is the standard reponse we use in our API when
    deleting a single entry.
    '''

    '''
    We request the deletion. All functions for deleting elements from a collection are suposed to return how many
    elements were really removed from the collection.
    '''
    db_response = ExampleDbController.get_instance().delete_entry_by_uuid(uuid)

    '''
    We use a special function that automatically creates API responses for deletion operation. Note that it is different from the
    "process_normal_database_response" we used in the endpoint for listing entries. The function we use here takes care of
    creating the standarized response for a deletion operation.
    '''
    return request.state.response_handler.process_deletion_database_response(
        db_response, True
    )
