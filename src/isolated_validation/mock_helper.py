import builtins
import importlib
import pkgutil
import os
import sys
import inspect
import re
import urllib
import ast
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO, BufferedReader, TextIOWrapper, BufferedWriter
from pathlib import Path
from urllib.parse import urlparse
from collections.abc import Iterator
from enum import Enum
from threading import Thread
from zoneinfo import ZoneInfo
import logging
import zlib

reference_dict = {}

def clear_reference_dict():
    global reference_dict
    reference_dict.clear()

def import_all_modules_from_folder(folder_path):
    """
    Dynamically imports all modules from a given folder.
    
    Args:
        folder_path (str): Absolute path to the folder containing modules/packages.
    """

    folder_path = os.path.abspath(folder_path)
    parent_folder = os.path.dirname(folder_path)
    
    if parent_folder not in sys.path:
        sys.path.insert(0, parent_folder)

    package_name = os.path.basename(folder_path)

    for _, module_name, _ in pkgutil.walk_packages([folder_path], f"{package_name}."):
        full_module_name = f"{module_name}"
        try:
            module = importlib.import_module(full_module_name)
            
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, type):
                    globals()[f"{module_name}.{name}"] = obj
        except Exception as e:
            continue


import_all_modules_from_folder("src")

class PeekableIterator:
    def __init__(self, iterable):
        self.iterable = iterable
        self.iterator = iter(iterable)
        self.peeked = None
        self.history = []
        self.index = -1

    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= 0:
            value = self.history[self.index]
            self.index -= 1
            return value

        if self.peeked is not None:
            next_item = self.peeked
            self.peeked = None
        else:
            next_item = next(self.iterator)

        self.history.append(next_item)
        return next_item

    def hasNext(self):
        if self.peeked is None:
            try:
                self.peeked = next(self.iterator)
            except StopIteration:
                return False
        return True

    def previous(self):
        if self.hasPrevious():
            self.index += 1
            return self.history[self.index]
        raise StopIteration("No previous elements.")

    def hasPrevious(self):
        return self.index + 1 < len(self.history)

    def to_list(self):
        result = self.history[:]
        if self.peeked is not None:
            result.append(self.peeked)

        if isinstance(self.iterable, PeekableIterator):
            remaining = self.iterable.to_list()[len(self.history):]  # Get only unseen elements
        else:
            remaining = list(self.iterator)

        return result + remaining
    
class HelpFormatterTest_AnonymousClass_1:
    def __call__(self, opt1, opt2):
        opt1_key_casefold =  opt1.getKey().casefold()
        opt2_key_casefold =  opt2.getKey().casefold()
        return (opt2_key_casefold > opt1_key_casefold) - (opt2_key_casefold < opt1_key_casefold)

class CRC32:
    def __init__(self):
        self._crc = 0

    def update(self, data: bytes):
        self._crc = zlib.crc32(data, self._crc)

    def get_value(self):
        return self._crc & 0xffffffff  # match Java unsigned CRC32
    
    def getValue(self):
        return self._crc & 0xffffffff 

    def reset(self):
        self._crc = 0

charset_map = {
    "UTF-8": "utf-8",
    "UTF8": "utf-8",
    "UTF-16": "utf-16",
    "UTF-16BE": "utf-16-be",
    "UTF-16LE": "utf-16-le",
    "US-ASCII": "ascii",
    "ISO-8859-1": "iso-8859-1",
    "ISO-8859-2": "iso-8859-2",
    "ISO-8859-15": "iso-8859-15",
    "windows-1252": "cp1252",
    "windows-1251": "cp1251",
    "Big5": "big5",
    "GB2312": "gb2312",
    "GB18030": "gb18030",
    "Shift_JIS": "shift_jis",
    "EUC-JP": "euc_jp",
    "KOI8-R": "koi8_r",
    "ISO-2022-JP": "iso2022_jp"
}

java_to_python_locale = {
    "en": "en_US.UTF-8",
    "en_US": "en_US.UTF-8",
    "en_GB": "en_GB.UTF-8",
    "fr": "fr_FR.UTF-8",
    "fr_FR": "fr_FR.UTF-8",
    "de": "de_DE.UTF-8",
    "de_DE": "de_DE.UTF-8",
    "es": "es_ES.UTF-8",
    "es_ES": "es_ES.UTF-8",
    "it": "it_IT.UTF-8",
    "it_IT": "it_IT.UTF-8",
    "pt": "pt_PT.UTF-8",
    "pt_PT": "pt_PT.UTF-8",
    "pt_BR": "pt_BR.UTF-8",
    "zh": "zh_CN.UTF-8",
    "zh_CN": "zh_CN.UTF-8",
    "zh_TW": "zh_TW.UTF-8",
    "ja": "ja_JP.UTF-8",
    "ja_JP": "ja_JP.UTF-8",
    "ko": "ko_KR.UTF-8",
    "ko_KR": "ko_KR.UTF-8",
    "ru": "ru_RU.UTF-8",
    "ru_RU": "ru_RU.UTF-8",
    "ar": "ar_EG.UTF-8",
    "ar_EG": "ar_EG.UTF-8",
    "hi": "hi_IN.UTF-8",
    "hi_IN": "hi_IN.UTF-8",
}


type_map = {
    "java.lang.Byte": "int",
    "java.lang.Boolean": "bool",
    "java.lang.Character": "str",
    "java.lang.IllegalStateException": "RuntimeError",
    "java.lang.IllegalArgumentException": "ValueError",
    "java.lang.Integer": "int",
    "java.lang.Float": "float",
    "java.lang.Object": "object",
    "java.lang.String": "str",
    "java.lang.Throwable": "Exception",
    "java.io.InputStream": "io.IOBase",
    "java.io.OutputStream": "io.IOBase",
    "java.io.ByteArrayInputStream": "io.BytesIO",
    "java.io.ByteArrayOutputStream": "io.BytesIO",
    "java.io.IOException": "OSError",
    "java.io.UnsupportedEncodingException": "ValueError",
    "java.util.Arrays$ArrayList": "list",
    "java.util.ArrayList": "list",
    "java.util.LinkedList": "list",
    "java.util.HashMap": "dict",
    "java.util.HashSet": "set",
    "java.util.Iterator": "PeekableIterator",
    "java.util.LinkedHashMap": "dict",
    "java.util.Map": "dict",
    "java.util.TreeMap": "dict",
    "ArrayList": "list",
    "LinkedList": "list",
    "byte": "int",
    "int": "int",
    "long": "int",
    "char": "str",
    "boolean": "bool",
    "null": "None",
    "java.lang.Long": "int",
    "Assert": "unittest.TestCase",
    "java.lang.NumberFormatException": "ValueError",
    "java.util.ArrayIndexOutOfBoundsException": "IndexError",
    "java.lang.UnsupportedOperationException": "RuntimeError",
    "java.lang.ClassNotFoundException": "ModuleNotFoundError",
    "java.util.Enumeration": "PeekableIterator",
    "java.lang.RuntimeException": "RuntimeError",
    "java.util.ListIterator": "PeekableIterator",
    "java.lang.CloneNotSupportedException": "TypeError",
    "java.util.Vector": "list",
    "java.lang.Double": "float",
    "java.util.Properties": "dict",
    "java.io.FileNotFoundException": "FileNotFoundError",
    "java.net.MalformedURLException": "ValueError",
    "java.util.Arrays": "list",
    "java.lang.Class": "type",
    "java.util.Collections$UnmodifiableRandomAccessList": "tuple",
    "java.util.Collections$SingletonList": "list",
    "java.util.Comparator": "typing.Callable",
    "java.lang.reflect.Constructor": "typing.Callable",
    "java.lang.reflect.Method": "typing.Callable",
    "java.io.PrintWriter": "io.StringIO",
    "java.lang.StringBuffer": "io.StringIO",
    "java.lang.Number": "numbers.Number",
    "java.net.URL": "urllib.parse.ParseResult",
    "java.net.URI": "urllib.parse.ParseResult",
    "java.util.Date": "datetime.datetime",
    "java.util.Calendar": "datetime.datetime",
    "java.time.Instant": "datetime.datetime",
    "java.time.Clock": "datetime.datetime",
    "java.util.concurrent.atomic.AtomicInteger": "int",
    "java.io.File": "pathlib.Path",
    "java.util.Collections$UnmodifiableCollection": "tuple",
    "java.io.FileInputStream": "io.FileIO",
    "java.io.FileOutputStream": "io.FileIO",
    "java.util.LinkedHashMap$LinkedValues": "dict_values",
    "java.util.LinkedHashMap$LinkedKeySet": "dict_keys",
    "java.lang.Short": "int",
    "java.util.Collections$EmptyList": "tuple",
    "java.util.RandomAccessSubList": "list",
    "java.io.BufferedInputStream": "io.BufferedReader",
    "java.io.BufferedOutputStream": "io.BufferedWriter",
    "java.io.StringReader": "io.StringIO",
    "java.io.StringWriter": "io.StringIO",
    "java.lang.StringBuilder": "io.StringIO",
    "java.io.BufferedReader": "io.BufferedReader",
    "java.lang.CharSequence": "str",
    "java.util.stream.Stream": "PeekableIterator",
    "java.io.InputStreamReader": "io.TextIOWrapper",
    "java.io.OutputStreamWriter": "io.TextIOWrapper",
    "java.io.PipedReader": "io.BytesIO",
    "java.io.PipedWriter": "io.BytesIO",
    "java.io.FilterInputStream": "io.BufferedReader",
    "java.io.FilterOutputStream": "io.BufferedWriter",
    "java.io.PipedInputStream": "io.BytesIO",
    "java.io.PipedOutputStream": "io.BytesIO",
    "java.io.PrintStream": "io.BytesIO",
    "java.lang.AssertionError": "AssertionError",
    "java.util.concurrent.ThreadFactory": "threading.Thread",
    "java.util.concurrent.Executors$DefaultThreadFactory": "threading.Thread",
    "java.lang.IndexOutOfBoundsException": "IndexError",
    "java.math.BigInteger": "int",
    "java.math.BigDecimal": "float",
    "java.lang.reflect.Modifier": "str",
    "java.util.regex.Pattern": "str",
    "java.util.regex.Matcher": "re.Match",
    "java.util.Locale": "str",
    "java.util.zip.CRC32": "CRC32",
    "java.util.Scanner": "PeekableIterator",
    "java.net.URISyntaxException": "ValueError",
    "java.lang.ClassCastException": "TypeError",
    "java.nio.charset.UnsupportedCharsetException": "LookupError",
    "java.util.concurrent.TimeUnit": "datetime.timedelta",
    "java.time.temporal.ChronoUnit": "datetime.timedelta",
    "java.time.Duration": "datetime.timedelta",
    "java.util.BitSet": "list",
    "java.nio.charset.Charset": "str",
    "java.util.TimeZone": "datetime.timezone",
    "sun.util.calendar.ZoneInfo": "zoneinfo.ZoneInfo",
    "RuntimeException": "RuntimeError",
    "java.nio.CharBuffer": "bytearray",
    "java.nio.HeapCharBuffer": "bytearray",
    "java.lang.Appendable": "io.StringIO"
} 

def retrieve_from_type_map(class_name, default):
    if class_name.startswith("src."):
        if "$" in class_name:
            return class_name.replace("$", ".")
        else:
            last =  class_name.split(".")[-1]
            return f"{class_name}.{last}"
    return type_map.get(class_name, default)
        
def convert_to_python(json_obj, force_new_object=False):
    """
    Recursively convert the JSON object from Java's customToString()
    to the corresponding Python objects based on the type_map.
    Java memory address used to avoid duplicate object creation when pointer aliases
    Flag `force_new_object` only set to `True` when creating dummy objects for equivalence check.
    """
    global reference_dict
    java_type = json_obj.get("type")
    if not java_type:
        return None

    if "value" in json_obj:
        if json_obj.get("value") is None:
            return None

    python_type = retrieve_from_type_map(java_type, java_type)

    if python_type == 'str':
        str_val = json_obj.get("value", None)
        memory_address = json_obj.get("memory_address")
        if memory_address and memory_address in reference_dict:
            return reference_dict[memory_address]
        if memory_address and memory_address not in reference_dict:
            reference_dict[memory_address] = str_val
        return str_val
    elif python_type == 'int':
        int_val = json_obj.get("value", None)
        if int_val is not None:
            int_val = int(int_val)
        memory_address = json_obj.get("memory_address")
        if memory_address and memory_address in reference_dict:
            return reference_dict[memory_address]
        if memory_address and memory_address not in reference_dict:
            reference_dict[memory_address] = int_val
        return int_val
    elif python_type == 'float' or python_type == 'numbers.Number':
        float_val = json_obj.get("value", None)
        if float_val is not None:
            float_val = float(float_val)
        memory_address = json_obj.get("memory_address")
        if memory_address and memory_address in reference_dict:
            return reference_dict[memory_address]
        if memory_address and memory_address not in reference_dict:
            reference_dict[memory_address] = float_val
        return float_val
    elif python_type == 'bool':
        bool_val = json_obj.get("value", None)
        if bool_val == "true":
            bool_val = True
        elif bool_val == "false":
            bool_val = False
        else:
            bool_val = None
        memory_address = json_obj.get("memory_address")
        if memory_address and memory_address in reference_dict:
            return reference_dict[memory_address]
        if memory_address and memory_address not in reference_dict:
            reference_dict[memory_address] = bool_val
        return bool_val
    elif python_type == 'tuple':
        collection_elements = json_obj.get("collection_elements", [])
        tuple_object = tuple([convert_to_python(elem, force_new_object=force_new_object) for elem in collection_elements])
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return tuple_object
        if memory_address in reference_dict:
            return reference_dict[memory_address]
        else:
            reference_dict[memory_address] = tuple_object
            return reference_dict[memory_address]
    elif python_type == 'list' or python_type.endswith("[]"):
        lst = json_obj.get("collection_elements", [])
        list_object = [convert_to_python(elem, force_new_object=force_new_object) for elem in lst]
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return list_object
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = list_object
                return reference_dict[memory_address]
            reference_dict[memory_address].clear()
            reference_dict[memory_address].extend(list_object)
        else:
            reference_dict[memory_address] = list_object
        return reference_dict[memory_address]
    elif python_type == 'dict_keys':
        key_set = json_obj.get("collection_elements", None)
        keys = [convert_to_python(elem, force_new_object=force_new_object) for elem in key_set]
        dummy_dict_keys = {keys[i]: i for i in range(len(keys))}.keys()
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return dummy_dict_keys
        reference_dict[memory_address] = dummy_dict_keys
        return reference_dict[memory_address]
    elif python_type == 'dict_values':
        lst = json_obj.get("collection_elements", None)
        values = [convert_to_python(elem, force_new_object=force_new_object) for elem in lst]
        dummy_dict_values = {i: values[i] for i in range(len(values))}.values()
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return dummy_dict_values
        reference_dict[memory_address] = dummy_dict_values
        return reference_dict[memory_address]
    elif python_type == 'set':
        elements = json_obj.get("collection_elements", set())
        set_object = set()
        for element in elements:
            set_object.add(convert_to_python(element, force_new_object=force_new_object))
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return set_object
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = set_object
                return reference_dict[memory_address]
            reference_dict[memory_address].clear()
            reference_dict[memory_address].update(set_object)
        else:
            reference_dict[memory_address] = set_object
        return reference_dict[memory_address]
    elif python_type == 'dict':
        keys = json_obj.get("keys", [])
        values = json_obj.get("values", [])
        dict_object = {convert_to_python(key, force_new_object=force_new_object): convert_to_python(value, force_new_object=force_new_object) for key, value in zip(keys, values)}
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return dict_object
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = dict_object
                return reference_dict[memory_address]
            reference_dict[memory_address].clear()
            reference_dict[memory_address].update(dict_object)
        else:
            reference_dict[memory_address] = dict_object
        return reference_dict[memory_address]
    elif python_type == "bytearray":
        elements = json_obj.get("buffer_elements", [])
        ba = bytearray()
        for element in elements:
            char_value = convert_to_python(element, force_new_object=force_new_object)
            if isinstance(char_value, str):
                ba.extend(char_value.encode("utf-8"))
            elif isinstance(char_value, int):
                ba.append(char_value)
            else:
                raise TypeError(f"Unsupported element type in CharBuffer: {type(char_value)}")
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return ba
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = ba
                return reference_dict[memory_address]
            reference_dict[memory_address].clear()
            reference_dict[memory_address].extend(ba)
        else:
            reference_dict[memory_address] = ba
        return reference_dict[memory_address]
    elif python_type == 'Exception':
        exception_cls = getattr(builtins, retrieve_from_type_map(json_obj.get("throwable_type", "java.lang.Throwable"), "Exception"))
        return exception_cls(json_obj.get("message", None))
    elif python_type == 'CRC32':
        crc_value = int(json_obj.get("value", 0))
        crc_object = CRC32()
        crc_object._crc = crc_value
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return crc_object
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = crc_object
                return reference_dict[memory_address]
            reference_dict[memory_address]._crc = crc_value
            return reference_dict[memory_address]
        else:
            reference_dict[memory_address] = crc_object
            return reference_dict[memory_address]
    elif python_type == 'PeekableIterator':
        peekable_iterator_object = PeekableIterator([])
        collection = json_obj.get("collection_details", {}).get("collection_elements", None)
        if collection is None:
            keys = json_obj.get("collection_details", {}).get("keys", None)
            values = json_obj.get("collection_details", {}).get("values", None)
            if keys is None or values is None:
                return peekable_iterator_object
            else:
                peekable_iterator_object = PeekableIterator({
                    convert_to_python(key, force_new_object=force_new_object): convert_to_python(value, force_new_object=force_new_object) for key, value in zip(keys, values)
                })
        else:
            peekable_iterator_object = PeekableIterator([convert_to_python(elem, force_new_object=force_new_object) for elem in collection])
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return peekable_iterator_object
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = peekable_iterator_object
                return reference_dict[memory_address]
            reference_dict[memory_address].__dict__.clear()
            reference_dict[memory_address].__dict__.update(peekable_iterator_object.__dict__)
        else:
            reference_dict[memory_address] = peekable_iterator_object
        return reference_dict[memory_address]
    elif python_type == "urllib.parse.ParseResult":
        return urlparse(json_obj.get("value", ""))
    elif python_type == "io.BytesIO":
        byte_array_json = json_obj.get("byte_array", None)
        if byte_array_json is None:
            byte_array_json = json_obj.get("sink_details", None)
            if byte_array_json is None:
                byte_array = []
            else:
                byte_array = convert_to_python(json_obj.get("sink_details").get("byte_array"))
        else:
            byte_array = convert_to_python(byte_array_json)
        byte_buffer = bytes([x & 0xFF for x in byte_array])
        if java_type == "java.io.ByteArrayInputStream":
            bytes_io_object = BytesIO(byte_buffer)
            bytes_io_object.seek(int(json_obj.get("position", 0)))
        else:
            size = int(json_obj.get("size", 0))
            bytes_io_object = BytesIO(byte_buffer[:size])
            if "position" in json_obj:
                bytes_io_object.seek(int(json_obj.get("position", 0)))
            else:
                bytes_io_object.seek(size)
            
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return bytes_io_object
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = bytes_io_object
                return reference_dict[memory_address]
            reference_dict[memory_address].seek(0)
            reference_dict[memory_address].truncate(0)
            reference_dict[memory_address].write(bytes_io_object.getvalue())
            reference_dict[memory_address].seek(int(json_obj.get("position", 0)))
        else:
            reference_dict[memory_address] = bytes_io_object
        return reference_dict[memory_address]
    elif python_type == "io.StringIO":
        if json_obj.get("special_note", None) is not None:
            if json_obj.get("special_note") == "System.out":
                return sys.stdout
            elif json_obj.get("special_note") == "System.err":
                return sys.stderr
            elif json_obj.get("special_note") == "byte_stream":
                return convert_to_python(json_obj.get("byte_stream"))
        content = json_obj.get("content", None)
        position = int(json_obj.get("position", 0))
        if content is None:
            content = json_obj.get("value", "")
            position = len(content)
        string_io_object = StringIO()
        string_io_object.write(content)
        if "position" in json_obj:
            string_io_object.seek(position)
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return string_io_object
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = string_io_object
                return reference_dict[memory_address]
            try:
                reference_dict[memory_address].seek(0)
            except Exception:
                reference_dict[memory_address] = string_io_object
                return reference_dict[memory_address]
            reference_dict[memory_address].truncate(0)
            reference_dict[memory_address].write(string_io_object.getvalue())
            if "position" in json_obj:
                reference_dict[memory_address].seek(int(json_obj.get("position")))
        else:
            reference_dict[memory_address] = string_io_object
        return reference_dict[memory_address]
    elif python_type == "logging.Logger":
        return logging.getLogger("my_logger")
    elif python_type == "re.Match":
        try:
            pattern_str = json_obj.get("pattern_str", "")
            input_str = json_obj.get("input_str", "")
            region_start = json_obj.get("region_start", 0)
            region_end = json_obj.get("region_end", len(input_str))
            try:
                pattern = re.compile(pattern_str)
                sub_input = input_str[region_start:region_end]
                match = pattern.search(sub_input)
                return match
            except re.error:
                pattern = re.compile(java_to_python_regex(pattern_str))
                sub_input = input_str[region_start:region_end]
                match = pattern.search(sub_input)
                return match
        except Exception:
            return None
    elif python_type == "io.BufferedReader":
        if json_obj.get("stream_type", None) is not None:
            if json_obj.get("stream_type") == "byte_stream":
                byte_stream = convert_to_python(json_obj.get("stream_details"))
                content_bytes = byte_stream.getvalue()
                position = byte_stream.tell()
            elif json_obj.get("stream_type") == "file_stream":
                obj = convert_to_python(json_obj.get("stream_details"))
                return BufferedReader(obj.buffer.raw)
            else:
                return None
        elif json_obj.get("special_note", None) is not None:
            if json_obj.get("special_note") == "System.out":
                return TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
            elif json_obj.get("special_note") == "System.err":
                return TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
            elif json_obj.get("special_note") == "byte_stream":
                byte_stream = convert_to_python(json_obj.get("byte_stream"))
                content_bytes = byte_stream.getvalue()
                position = byte_stream.tell()
        else:
            content = json_obj.get("content", "")
            position = int(json_obj.get("position", 0))
            content_bytes = content.encode("utf-8") 
            byte_stream = BytesIO(content_bytes)
            byte_stream.seek(position)
        br = BufferedReader(byte_stream)
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return br
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = br
                return reference_dict[memory_address]
            underlying = reference_dict[memory_address].raw
            underlying.seek(0)
            underlying.truncate(0)
            underlying.write(content_bytes)
            underlying.seek(position)
        else:
            reference_dict[memory_address] = br
        return reference_dict[memory_address]
    elif python_type == "io.BufferedWriter":
        if json_obj.get("stream_type") == "byte_stream":
            byte_stream = convert_to_python(json_obj.get("stream_details"))
            content_bytes = obj.getvalue()
            position = obj.tell()
            bw = BufferedWriter(byte_stream)
            memory_address = json_obj.get("memory_address")
            bw.seek(0)
            if force_new_object or not memory_address:    
                return bw
            if memory_address in reference_dict:
                if reference_dict[memory_address] is None:
                    reference_dict[memory_address] = bw
                    return reference_dict[memory_address]
                underlying = reference_dict[memory_address].raw
                underlying.seek(0)
                underlying.truncate(0)
                underlying.write(content_bytes)
                underlying.seek(position)
            else:
                reference_dict[memory_address] = bw
            return reference_dict[memory_address]
        elif json_obj.get("stream_type") == "file_stream":
            obj = convert_to_python(json_obj.get("stream_details"))
            return BufferedWriter(obj.buffer.raw)
        else:
            return None
    elif python_type == "src.main.org.apache.commons.fileupload.util.LimitedInputStream.LimitedInputStream"\
        or python_type == "src.main.org.apache.commons.codec.binary.BaseNCodecInputStream.BaseNCodecInputStream"\
        or python_type == "src.main.org.apache.commons.codec.binary.Base16InputStream.Base16InputStream"\
        or python_type == "src.main.org.apache.commons.codec.binary.Base32InputStream.Base32InputStream"\
        or python_type == "src.main.org.apache.commons.codec.binary.Base64InputStream.Base64InputStream"\
        or python_type == "src.main.org.apache.commons.codec.binary.BaseNCodecOutputStream.BaseNCodecOutputStream"\
        or python_type == "src.main.org.apache.commons.codec.binary.Base16OutputStream.Base16OutputStream"\
        or python_type == "src.main.org.apache.commons.codec.binary.Base32OutputStream.Base32OutputStream"\
        or python_type == "src.main.org.apache.commons.codec.binary.Base64OutputStream.Base64OutputStream":
        underlying = None
        if json_obj.get("stream_type", None) is not None:
            if json_obj.get("stream_type") == "byte_stream":
                underlying = convert_to_python(json_obj.get("stream_details"))
            elif json_obj.get("stream_type") == "file_stream":
                underlying = convert_to_python(json_obj.get("stream_details")).buffer.raw
            else:
                underlying = BytesIO()
        else:
            underlying = BytesIO()
        clazz = globals().get(python_type)
        obj = clazz.__new__(clazz)
        BufferedReader.__init__(obj, underlying)
        className = obj.__class__.__name__
        instance_fields = json_obj.get("instance_fields", {})
        for field_name, field_details in instance_fields.items():
            if "modifier" in field_details:
                if field_details.get("modifier") == "private":
                    setattr(obj, "_" + className + "__" + field_name, convert_to_python(field_details))
                elif field_details.get("modifier") == "protected":
                    setattr(obj, "_" + field_name, convert_to_python(field_details))
                else:
                    setattr(obj, field_name, convert_to_python(field_details))
            else:
                setattr(obj, field_name, convert_to_python(field_details))
        return obj
    elif python_type == "src.main.org.apache.commons.csv.ExtendedBufferedReader.ExtendedBufferedReader":
        content = json_obj.get("content", "")
        content_bytes = content.encode("utf-8")
        byte_stream = BytesIO(content_bytes)
        extendedBufferedReader_clazz = globals().get(python_type)
        extendedBufferedReader_obj = extendedBufferedReader_clazz.__new__(extendedBufferedReader_clazz)
        BufferedReader.__init__(extendedBufferedReader_obj, byte_stream)
        className = extendedBufferedReader_obj.__class__.__name__
        instance_fields = json_obj.get("instance_fields", {})
        for field_name, field_details in instance_fields.items():
            if "modifier" in field_details:
                if field_details.get("modifier") == "private":
                    setattr(extendedBufferedReader_obj, "_" + className + "__" + field_name, convert_to_python(field_details))
                elif field_details.get("modifier") == "protected":
                    setattr(extendedBufferedReader_obj, "_" + field_name, convert_to_python(field_details))
                else:
                    setattr(extendedBufferedReader_obj, field_name, convert_to_python(field_details))
            else:
                setattr(extendedBufferedReader_obj, field_name, convert_to_python(field_details))
        extendedBufferedReader_obj.seek(extendedBufferedReader_obj._ExtendedBufferedReader__position)
        return extendedBufferedReader_obj   
    elif python_type == "io.FileIO":
        file_path = json_obj.get("file_path")
        position = json_obj.get("position")
        file_size = json_obj.get("file_size")
        file_io_object = None
        try:
            file_io_object = open(file_path, 'r')
            actual_size = file_io_object.seek(0, 2)  # Move to the end of the file to get its size
            if actual_size != file_size:
                print(f"Warning: File size mismatch. Expected {file_size}, but got {actual_size}.")
            file_io_object.seek(position)  # Position the pointer at the given `position`
        except FileNotFoundError:
            print(f"Error: The file at {file_path} does not exist.")
        except Exception as e:
            print(f"Error: {str(e)}")
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return file_io_object
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = file_io_object
                return reference_dict[memory_address]
            reference_dict[memory_address].seek(0)
            reference_dict[memory_address].truncate(0)
            reference_dict[memory_address].write(file_io_object.buffer.getvalue().decode("utf-8"))
            reference_dict[memory_address].seek(int(json_obj.get("position")))
        else:
            reference_dict[memory_address] = file_io_object
        return reference_dict[memory_address]
    elif python_type == 'io.TextIOWrapper':
        encoding = json_obj.get("encoding", "utf-8")
        special_note = json_obj.get("special_note", "")
        textIOWrapper_obj = None
        if special_note == "System.in":
            textIOWrapper_obj = TextIOWrapper(sys.stdin.buffer, encoding=encoding)
        elif special_note == "byte_stream":
            textIOWrapper_obj = TextIOWrapper(convert_to_python(json_obj.get("byte_stream")), encoding=encoding)
        elif special_note == "file_stream":
            textIOWrapper_obj = convert_to_python(json_obj.get("file_stream"))
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return textIOWrapper_obj
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = textIOWrapper_obj
                return reference_dict[memory_address]
            existing_wrapper = reference_dict[memory_address]
            try:
                if hasattr(textIOWrapper_obj.buffer, 'getvalue'):
                    content_bytes = textIOWrapper_obj.buffer.getvalue()
                    existing_wrapper.buffer.seek(0)
                    existing_wrapper.buffer.truncate(0)
                    existing_wrapper.buffer.write(content_bytes)
                    existing_wrapper.buffer.seek(0)
                else:
                    reference_dict[memory_address].seek(0)
                    reference_dict[memory_address].truncate(0)
                    reference_dict[memory_address].write(textIOWrapper_obj.buffer.getvalue().decode("utf-8"))
                    reference_dict[memory_address].seek(int(json_obj.get("file_stream").get("position")))
            except Exception:
                reference_dict[memory_address] = textIOWrapper_obj
        else:
            reference_dict[memory_address] = textIOWrapper_obj
        return reference_dict[memory_address]
    elif python_type == 'type':
        java_clazz_name = json_obj.get("value", "null")
        if java_clazz_name.startswith("[L"):
            return list
        python_clazz_name = retrieve_from_type_map(java_clazz_name, java_clazz_name)
        if python_clazz_name == 'None':
            return None
        try:
            clazz = getattr(builtins, python_clazz_name)
            return clazz
        except AttributeError:
            try:
                clazz = globals().get(python_clazz_name)
                if clazz is None:
                    module_name, class_name = python_clazz_name.rsplit('.', 1)
                    module = importlib.import_module(module_name)
                    clazz = getattr(module, class_name)
                return clazz
            except (ValueError, ImportError, AttributeError):
                clazz = globals().get(retrieve_from_type_map("src.main." + java_clazz_name, None))
                if not clazz:
                    clazz = globals().get(retrieve_from_type_map("src.test." + java_clazz_name, None))
                if not clazz:
                    return None
                else:
                    return clazz
    elif python_type == 'pathlib.Path':
        path_str = json_obj.get("value", None)
        return Path(path_str)
    elif python_type == 'datetime.timezone' or python_type == 'zoneinfo.ZoneInfo':
        tz_id = json_obj.get("id")
        try:
            tz = ZoneInfo(tz_id)
        except Exception:
            tz = datetime.timezone(
                timedelta(milliseconds=json_obj.get("offset"))
            )
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return tz
        else:
            if memory_address in reference_dict:
                return reference_dict[memory_address]
            else:
                reference_dict[memory_address] = tz
                return reference_dict[memory_address]
    elif python_type == 'datetime.datetime':
        datetime_object = datetime(1970, 1, 1)
        if "timestamp" in json_obj:
            ts = json_obj.get("timestamp")
            tz = timezone.utc if "timezone" not in json_obj else ZoneInfo(json_obj.get("timezone"))
            datetime_object = datetime.fromtimestamp(ts, tz)
        elif "instant" in json_obj:
            datetime_object = datetime.fromisoformat(json_obj.get("instant"))
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return datetime_object
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = datetime_object
                return reference_dict[memory_address]
            delta = datetime_object - reference_dict[memory_address]
            reference_dict[memory_address] = reference_dict[memory_address] + delta
        else:
            reference_dict[memory_address] = datetime_object
        return reference_dict[memory_address]
    elif python_type == 'datetime.timedelta':
        td = timedelta(0)
        seconds = json_obj.get("seconds", 0)
        nanos = json_obj.get("nanos", 0)
        total_microseconds = seconds * 1_000_000 + nanos / 1_000
        days, rem = divmod(total_microseconds, 86_400_000_000)
        seconds, rem = divmod(rem, 1_000_000)
        microseconds = rem
        if "nanos" in json_obj:
            try:
                td = timedelta(days=days, seconds=seconds, microseconds=microseconds)
            except OverflowError:
                td = timedelta.max
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return td
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = td
                return reference_dict[memory_address]
            delta = td - reference_dict[memory_address]
            reference_dict[memory_address] += delta
        else:
            reference_dict[memory_address] = td
        return reference_dict[memory_address]
    elif python_type == 'threading.Thread':
        return Thread(target=None, name=None, args=(), kwargs=None, daemon=False)
    elif python_type == 'typing.Callable':
        if json_obj.get("ctor_declaring_class", None) is not None:
            return globals().get(retrieve_from_type_map(json_obj.get("ctor_declaring_class"), None), None)
        elif json_obj.get("method_declaring_class", None) is not None:
            clazz = globals().get(retrieve_from_type_map(json_obj.get("method_declaring_class"), None), None)
            if clazz is None:
                return None
            func_name = json_obj.get("name")
            if json_obj.get("modifier") == "protected":
                func_name = "_" + func_name
            elif json_obj.get("modfier") == "private":
                func_name = f"_{clazz.__name__}__{func_name}"
            if hasattr(clazz, func_name):
                return getattr(clazz, func_name)
            else:
                return None
        callable_instance_str = json_obj.get("value", None)
        callable_obj = None
        if "@" in callable_instance_str:
            callable_type = callable_instance_str.split("@")[0]
        callable_class = globals().get(retrieve_from_type_map('src.main.' + callable_type, None), None)
        if callable_class is not None:
            callable_obj = object.__new__(callable_class)
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return callable_obj
        if memory_address in reference_dict:
            if reference_dict[memory_address] is None:
                reference_dict[memory_address] = callable_obj
                return reference_dict[memory_address]
            reference_dict[memory_address].__call__ = callable_obj.__call__
        else:
            reference_dict[memory_address] = callable_obj
        return reference_dict[memory_address]
    elif "_AnonymousClass_" in python_type:
        return globals()[python_type]()
    elif python_type == 'None':
        return None
    else:
        return create_python_object(python_type, json_obj, force_new_object=force_new_object)


def extract_balanced_brackets(s: str, start: int):
    """
    From a starting index, return the content of the next balanced bracket section.
    """
    stack = []
    i = start
    in_string = False
    escape = False

    while i < len(s):
        c = s[i]
        if escape:
            escape = False
        elif c == "\\":
            escape = True
        elif c in "\"'":
            in_string = not in_string
        elif not in_string:
            if c == "[":
                stack.append("[")
            elif c == "]":
                if not stack:
                    return s[start:i].strip(), i
                stack.pop()
        i += 1
    return None, None


def extract_named_sections(s: str) -> dict:
    """
    Extracts sections like [ short {...} ] or [ long {...} ] into a dict
    with keys "short", "long", etc.
    """
    sections = {}
    pattern = re.compile(r"\[\s*(\w+)\s+")
    pos = 0
    while True:
        match = pattern.search(s, pos)
        if not match:
            break

        name = match.group(1)
        start = match.end()
        content, end = extract_balanced_brackets(s, start)
        if content is None:
            raise ValueError(f"Could not find balanced content for section '{name}' starting at position {start}")

        norm_blob = normalize_struct(content)
        try:
            parsed = ast.literal_eval(norm_blob)
        except Exception as e:
            raise ValueError(f"Failed to parse section '{name}': {e}\nOriginal:\n{content}")
        sections[name] = parsed
        pos = end + 1  # move to next match
    return sections

def normalize_struct(s: str) -> str:
    """
    Replace: K
    Java object refs -> <_anyobject_> placeholder
    Java class refs -> <class> placeholder
    `[ option: ... :: ... :: ... ]` (`Option` class specific structure) -> <object> placeholder
    Normalize key: value and key=value to 'key': value ). (Java HashMap <--> Python Dict)
    """
    s = re.sub(r'<[^>]+?object at 0x[0-9a-fA-F]+>', '"<_anyobject_>"', s)
    s = re.sub(r"\[ option:.*?::.*?::.*?\]", '"<_anyobject_>"', s)
    s = re.sub(r'class\s+[\w.$]+', '"<class>"', s)
    s = re.sub(r"<class\s+'[\w.]+'?>", '"<class>"', s)
    s = re.sub(r"(?<!['\"])(\b\w+)\s*[:=]\s*", r"'\1': ", s)
    return s


def logically_equal(java_str: str, py_str: str) -> bool:
    """ Check if two strings are equal according to CLI specifics """
    try:
        if java_str.strip().startswith("[ option:") and py_str.strip().startswith("[ option:"):
            norm_java = normalize_struct(java_str).strip()
            norm_py = normalize_struct(py_str).strip()
            return norm_java == norm_py
        java_sections = extract_named_sections(java_str)
        py_sections = extract_named_sections(py_str)
        if not java_sections or not py_sections:
            return False
        return java_sections == py_sections
    except Exception as e:
        print(f"Error during comparison: {e}")
        return False

def is_sublist(a, b):
    """Return True if list a is a sublist of list b."""
    if not a:
        return True
    len_a = len(a)
    return any(b[i:i+len_a] == a for i in range(len(b) - len_a + 1))

def java_to_python_regex(java_regex: str) -> str:
    """WIP: Auto-Convert Java regex strings to Python"""
    python_regex = java_regex.encode().decode('unicode_escape')
    python_regex = re.sub(r'\(\?<(\w+)>', r'(?P<\1>', python_regex)
    python_regex = re.sub(r'\\p\{Alpha\}', r'[A-Za-z]', python_regex)
    # to do ...
    return python_regex

def recursive_equal(obj1, obj2):
    """
    Recursively checks equality of two Python objects by comparing their attributes and values.
    """
    if isinstance(obj1, str) and isinstance(obj2, str):
        if obj1 == "TYPE WITH NO DIRECT PYTHON EQUIVALENT" or obj2 == "TYPE WITH NO DIRECT PYTHON EQUIVALENT":
            return True
    if isinstance(obj1, re.Match) or isinstance(obj2, re.Match):
        return True  # Disable `re.Match` checks because they're immutable
    if isinstance(obj1, logging.Logger) or isinstance(obj2, logging.Logger):
        return True  # Disable strict logger equality check as there're infinitely many possible correct implementations
    if obj1 is obj2:
        return True
    if isinstance(obj1, Enum) and isinstance(obj2, Enum):
        return obj1._name_ == obj2._name_ and recursive_equal(obj1._value_, obj2._value_)
    if isinstance(obj1, Exception) and isinstance(obj2, Exception):
        if issubclass(type(obj1), type(obj2)) or issubclass(type(obj2), type(obj1)):
            return True # Skip strict message equivalence check
        else:
            return False
    if isinstance(obj1, Thread) and isinstance(obj2, Thread):
        return True
    if isinstance(obj1, int) and isinstance(obj2, int) and obj1 != obj2:
        for obj in reference_dict.values():
            try:
                obj_hashcode = hash(obj)
            except TypeError:
                if hasattr(obj, '__dict__'):
                    for field1 in obj.__dict__:
                        try:
                            tuple_with_first_None_hashcode = hash((None, getattr(obj, field1)))
                        except TypeError:
                            pass
                        if tuple_with_first_None_hashcode == obj1:
                            return True
                        try:
                            tuple_with_second_None_hashcode = hash((getattr(obj, field1), None))
                        except TypeError:
                            pass
                        if tuple_with_second_None_hashcode == obj1:
                            return True
                        for field2 in obj.__dict__:
                            try:
                                field1_hashcode = hash(getattr(obj, field1))
                                field2_hashcode = hash(getattr(obj, field2))
                                tuple_hashcode = hash((getattr(obj, field1), getattr(obj, field2)))
                            except TypeError:
                                continue
                            if field1_hashcode == obj1 or field2_hashcode == obj1 or tuple_hashcode == obj1:
                                return True
                continue
            if obj_hashcode == obj1:
                return True
        return False
    if isinstance(obj1, timedelta) and isinstance(obj2, timedelta):
        TOLERANCE_SECONDS = 1e-6  # allow 1 microsecond difference (avoid numerical issues)
        if abs(obj1.total_seconds() - obj2.total_seconds()) < TOLERANCE_SECONDS:
            return True
        else:
            return False
    if isinstance(obj1, str) and isinstance(obj2, str) and not obj1 == obj2:
        if logically_equal(obj1, obj2):
            return True
        else:
            if obj1 and obj2:
                if charset_map.get(obj1, None) == obj2 or charset_map.get(obj2, None) == obj1:
                    return True
                elif java_to_python_regex(obj1) == obj2 or java_to_python_regex(obj2) == obj1:
                    return True
                elif java_to_python_locale.get(obj1, None) == obj2 or java_to_python_locale.get(obj2, None) == obj1:
                    return True
            return False
    if not isinstance(obj1, Iterator) and type(obj1) != type(obj2):
        return False
    if isinstance(obj1, (BytesIO, StringIO)):
        return obj1.getvalue() == obj2.getvalue()
    if isinstance(obj1, dict):
        if obj1.keys() != obj2.keys():
            return False
        return all([recursive_equal(obj1[key], obj2[key]) for key in obj1])
    elif isinstance(obj1, list):
        if len(obj1) != len(obj2):
            return False
        return all(recursive_equal(item1, item2) for item1, item2 in zip(obj1, obj2))
    elif isinstance(obj1, set):
        if len(obj1) != len(obj2):
            return False
        for item1 in obj1:
            if not any(recursive_equal(item1, item2) for item2 in obj2):
                return False
        return True
    elif isinstance(obj1, urllib.parse.ParseResult):
        return recursive_equal(obj1._asdict(), obj2._asdict())
    elif isinstance(obj1, datetime):
        return obj1.timestamp() == obj2.timestamp()
    elif isinstance(obj1, tuple):
        if len(obj1) != len(obj2):
            return False
        return all(recursive_equal(item1, item2) for item1, item2 in zip(obj1, obj2))
    elif isinstance(obj1, Iterator) and isinstance(obj2, Iterator):
        try:
            obj1_list = PeekableIterator(obj1).to_list()
            obj2_list = PeekableIterator(obj2).to_list()
            if recursive_equal(obj1_list, obj2_list):
                return True
            else:
                return is_sublist(obj2_list, obj1_list)
        except ValueError as e:
            if "I/O operation on closed file" in str(e) or "I/O operation on uninitialized object" in str(e):
                return True
            else:
                raise
        except TypeError:
            return True
    elif isinstance(obj1, type({}.values())) and isinstance(obj2, type({}.values())):
        return recursive_equal(list(obj1), list(obj2))
    elif hasattr(obj1, '__dict__') and hasattr(obj2, '__dict__'):
        obj1_dict_excluding_transient = {k: v for k, v in obj1.__dict__.items() if k in obj2.__dict__}
        return recursive_equal(obj1_dict_excluding_transient, obj2.__dict__)
    return obj1 == obj2


def get_parent_classes(clazz):
    """
    Get a list of all parent classes, excluding 'object'
    """
    return [base.__name__ for base in clazz.__bases__ if base is not object]

def set_object_instance_fields(obj, json_obj):
    """
    Update the instance fields of an object.
    Use the same instance if obj and json_obj is the same pointer(reference)
    """
    if obj is None:
        obj = convert_to_python(json_obj)
    if isinstance(obj, dict) or isinstance(obj, list) or isinstance(obj, set):
        obj.clear()
        converted_json_obj = convert_to_python(json_obj)
        if not converted_json_obj is obj:
            obj.extend(converted_json_obj)
    elif isinstance(obj, BytesIO) or isinstance(obj, StringIO):
        converted_json_obj = convert_to_python(json_obj)
        obj.seek(0)
        obj.truncate(0)
        converted_json_obj = convert_to_python(json_obj)
        if not converted_json_obj is obj:
            obj.write(converted_json_obj.getvalue())
            obj.seek(converted_json_obj.tell())
    elif isinstance(obj, BufferedReader) or isinstance(obj, BufferedWriter):
        converted_json_obj = convert_to_python(json_obj)
        if obj is converted_json_obj:
            return
        else:
            content_bytes = converted_json_obj.raw.getvalue()
            position = converted_json_obj.raw.tell()
            underlying = obj.raw
            underlying.seek(0)
            underlying.truncate(0)
            underlying.write(content_bytes)
            underlying.seek(position)
    elif "PeekableIterator" == type(obj).__name__:
        other = convert_to_python(json_obj)
        obj.iterable = other
        obj.iterator = other
        obj.peeked = None
        obj.history = []
        obj.index = -1
    else:
        className = obj.__class__.__name__
        instance_fields = json_obj.get("instance_fields", {})
        for field_name, field_details in instance_fields.items():
            field_name = field_name.split("_HIDDEN_FIELD___")[0]
            if "java.lang.Throwable" in field_details.get("declaring_class", ""):
                continue
            if "modifier" in field_details:
                if field_details.get("modifier") == "private":
                    declaring_class = field_details.get("declaring_class", None)
                    if declaring_class is not None:
                        setattr(obj, "_" + retrieve_from_type_map(declaring_class, declaring_class).split(".")[-1] + "__" + field_name, convert_to_python(field_details))
                    else:
                        setattr(obj, "_" + className + "__" + field_name, convert_to_python(field_details))
                elif field_details.get("modifier") == "protected":
                    setattr(obj, "_" + field_name, convert_to_python(field_details))
                else:
                    setattr(obj, field_name, convert_to_python(field_details))
            else:
                setattr(obj, field_name, convert_to_python(field_details))

def create_python_object(python_type, json_obj, force_new_object=False):
    """
    Create a Python object from the type and its instance/static fields.
    """
    global reference_dict
    try:
        if json_obj.get("value", None) is not None and json_obj.get("type", None) is not None:
            if json_obj.get("value").get("type", None) is not None:
                if json_obj.get("value").get("type") != json_obj.get("type"):
                    python_type = retrieve_from_type_map(json_obj.get("value").get("type"), python_type)
    except BaseException:
        return None
    try:
        clazz = globals().get(python_type)
    except (ValueError, ImportError, AttributeError):
        raise Exception(f"Could not find Python class for type: {python_type}")
    try:
        _ = issubclass(clazz, BaseException)
    except Exception:
        return "TYPE WITH NO DIRECT PYTHON EQUIVALENT"
    memory_address = json_obj.get("memory_address")
    is_new_object = memory_address not in reference_dict
    if memory_address and (json_obj.get("note") == "instance of self-referential field" or json_obj.get("note") == "circular_reference"):
        try:
            return reference_dict[memory_address]
        except Exception:
            return None
    if issubclass(clazz, BaseException):  # Ensure safe instantiation of exceptions
        try:
            obj = Exception.__new__(clazz)
        except TypeError:
            obj = clazz.__new__(clazz)
        obj.args = (json_obj.get("instance_fields", {}).get("cause", {}).get("message", ""),)
    elif issubclass(clazz, Enum):
        if json_obj.get("value") is not None:
            name = json_obj["value"].get("enum_name")
            value = convert_to_python(json_obj["value"].get("enum_value"), force_new_object=force_new_object)
        else:
            name = json_obj.get("enum_name")
            value = convert_to_python(json_obj.get("enum_value"), force_new_object=force_new_object)
        if name in clazz.__members__:
            clazz[name]._value_ = value
            return clazz[name]
        try:
            return clazz(value)
        except BaseException:
            obj = object.__new__(clazz)
            name = json_obj.get("value").get("enum_name") if json_obj.get("value", None) is not None else json_obj.get("enum_name")
            if json_obj.get("value", None) is not None:
                value = convert_to_python(json_obj.get("value").get("enum_value"), force_new_object=force_new_object)
            else: 
                value = convert_to_python(json_obj.get("enum_value"), force_new_object=force_new_object)
            obj._name_ = name
            obj._value_ = value
    else:
        try:
            obj = object.__new__(clazz)
        except TypeError:
            obj = clazz.__new__(clazz)
    if is_new_object:
        reference_dict[memory_address] = obj

    instance_fields = json_obj.get("instance_fields", {})
    if instance_fields == {}:
        if json_obj.get("value", None) is not None and json_obj.get("type", None) is not None:
            if json_obj.get("value").get("type", None) is not None:
                instance_fields = json_obj.get('value').get("instance_fields", {})
    for field_name, field_details in instance_fields.items():
        field_name = field_name.split("_HIDDEN_FIELD___")[0]
        if "java.lang.Throwable" in field_details.get("declaring_class", "") and field_details.get("shadowed", "") != "true":
            continue
        if "java.io." in field_details.get("declaring_class", "") and field_details.get("shadowed", "") != "true":
            continue
        if "modifier" in field_details:
            if field_details.get("modifier") == "private":
                declaring_class = field_details.get("declaring_class", None)
                if declaring_class is not None:
                    setattr(
                        obj, "_" +\
                        retrieve_from_type_map(declaring_class, declaring_class).split(".")[-1] +\
                        "__" +\
                        field_name, convert_to_python(field_details, force_new_object=force_new_object)
                    )
                else:
                    setattr(
                        obj,
                        "_" + python_type.split(".")[-1] + "__" + field_name,
                        convert_to_python(field_details, force_new_object=force_new_object)
                    )
            elif field_details.get("modifier") == "protected":
                setattr(obj, "_" + field_name, convert_to_python(field_details, force_new_object=force_new_object))
            else:
                setattr(obj, field_name, convert_to_python(field_details, force_new_object=force_new_object))
        else:
            setattr(obj, field_name, convert_to_python(field_details, force_new_object=force_new_object))

    static_fields = json_obj.get("static_fields", {})
    if static_fields == {}:
        if json_obj.get("value", None) is not None and json_obj.get("type", None) is not None:
            if json_obj.get("value").get("type", None) is not None:
                instance_fields = json_obj.get('value').get("static_fields", {})
    for field_name, field_details in static_fields.items():
        field_name = field_name.split("_HIDDEN_FIELD___")[0]
        if "java.lang.Throwable" in field_details.get("declaring_class", "") and field_details.get("shadowed", "") != "true":
            continue
        if "java.io." in field_details.get("declaring_class", "") and field_details.get("shadowed", "") != "true":
            continue
        if "modifier" in field_details:
            if field_details.get("modifier") == "private":
                declaring_class = field_details.get("declaring_class", None)
                if declaring_class is not None:
                    setattr(
                        clazz,
                        "_" + retrieve_from_type_map(declaring_class, declaring_class).split(".")[-1] + "__" + field_name,
                        convert_to_python(field_details, force_new_object=force_new_object)
                    )
                else:
                    setattr(
                        clazz,
                        "_" + python_type.split(".")[-1] + "__" + field_name,
                        convert_to_python(field_details, force_new_object=force_new_object)
                    )
            elif field_details.get("modifier") == "protected":
                setattr(clazz, "_" + field_name, convert_to_python(field_details, force_new_object=force_new_object))
            else:
                setattr(clazz, field_name, convert_to_python(field_details, force_new_object=force_new_object))
        else:
            setattr(clazz, field_name, convert_to_python(field_details, force_new_object=force_new_object))
    if force_new_object or not memory_address:
        return obj
    if not is_new_object:
        reference_dict[memory_address].__dict__.clear()
        reference_dict[memory_address].__dict__.update(obj.__dict__)
    else:
        reference_dict[memory_address] = obj
    return reference_dict[memory_address]

def update_static_fields(json_data):
    """
    Update static fields for classes based on a JSON list of dictionaries.
    Each dictionary specifies a class and its fields to update.
    """
    for class_data in json_data:
        for class_name, fields in class_data.items():
            python_class_name = retrieve_from_type_map(class_name, None)
            clazz = globals().get(python_class_name)
            if clazz is None:
                print(f"Class '{class_name}' not found in global scope.")
                continue
            for field_update in fields:
                for field_name, field_info in field_update.items():
                    field_name = field_name.split("_HIDDEN_FIELD___")[0]
                    field_value = convert_to_python(field_info.get("details"))
                    if "modifier" in field_info:
                        if field_info.get("modifier") == "private":
                            declaring_class = field_info.get("declaring_class", None)
                            if declaring_class is not None:
                                setattr(clazz, "_" + retrieve_from_type_map(declaring_class, declaring_class).split(".")[-1] + "__" + field_name, field_value)
                            else:
                                setattr(clazz, "_" + clazz.__name__ + "__" + field_name, field_value)
                        elif field_info.get("modifier") == "protected":
                            setattr(clazz, "_" + field_name, field_value)
                        else:
                            setattr(clazz, field_name, field_value)
                    else:
                        setattr(clazz, field_name, field_value)

def side_effect_is_correct(json_data):
    """
    Check if the current static fields are consistent with recorded JSON string
    """
    for class_data in json_data:
        for class_name, fields in class_data.items():
            clazz = globals().get(retrieve_from_type_map(class_name, None))
            if clazz is None:
                print(f"Class '{class_name}' not found in global scope.")
                continue
            for field_update in fields:
                for field_name, field_info in field_update.items():
                    field_name = field_name.split("_HIDDEN_FIELD___")[0]
                    field_value = convert_to_python(field_info.get("details"), force_new_object=True)
                    if "modifier" in field_info:
                        if field_info.get("modifier") == "private":
                            ref_obj = getattr(clazz, "_" + clazz.__name__ + "__" + field_name, None)
                        elif field_info.get("modifier") == "protected":
                            ref_obj = getattr(clazz, "_" + field_name, None)
                        else:
                            ref_obj = getattr(clazz, field_name, None)
                    else:
                        ref_obj = getattr(clazz, field_name, None)
                    if not recursive_equal(ref_obj, field_value):
                        return False
    return True
