# UUID guidelines

We have our own UUID format and a class for working with it. It is important to use the correct class for working with
UUIDs, to always maintain the consistency.

## Specification

Internally, our UUIDs are uint64 numbers, which means unsigned numbers which are 64bits long.

The UUIDs are divided in 2 parts:

- The first 32 bits contain the poisix date in which the UUID was created. This is why the start of 2 UUIDs created one right
after the other are very similar.

- The last 32 bits contain a random number.

However, working with uint64 values can cause various problems. Because of that, the UUIDs are normally represented as strings.
The correct string representation of an UUID is the hex representation of the number, separated in 4 groups of uppercase
characters, like this: "1234-5678-90AB-CDEF".

The string representation is what must be used normally, like when requesting an UUID as an API endpoint param, when returning
them in API responses and other similar opertations.

The number representation must be used only for cases in which it is clearly better than the string representation, like when
saving the value to a database (because numbers use less storage space).

## Helper class

There is a helper class called “Uuid64” in the [“orchestration/api/utils/uuid64.py”](../utils/uuid64.py) file, for working with
UUIDs. It provides a static function called "create_new_uuid()", which allows to create a new random UUID easilly, and also other
functions for creating instances from strings and numbers. The class also has functions for converting the UUID instances to
strings and numbers, to be able to return them in API responses, save them in the database, etc.

For example, if you have a number that represents a UUID and you want the string representation, you can so something like this:

```
string_uuid = Uuid64.from_mongo_value(val).to_formatted_str()
```

As an explanation, the `Uuid64.from_mongo_value(val)` part creates an instance of the Uuid64 class, representing the numeric
value sent to that function, and them the `.to_formatted_str()` returns the string representation of the UUID in that instance.

The class has a lot of comments, which you can check using the IDE tools or just by checking the class code.
