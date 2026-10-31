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

class JavaProcess:
    """Python stand-in for a java.lang.Process snapshot (subprocess.Popen-like surface)."""
    def __init__(self, pid=None, alive=False, exit_value=None, stdout=None, stderr=None, stdin=None):
        self.pid = pid
        self.alive = alive
        self.returncode = None if alive else exit_value
        self.stdout = stdout
        self.stderr = stderr
        self.stdin = stdin

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def isAlive(self):
        return self.alive

    def exitValue(self):
        if self.alive:
            raise RuntimeError("process has not exited")
        return self.returncode

    def waitFor(self):
        return self.returncode

    def __eq__(self, other):
        return isinstance(other, JavaProcess) and (self.pid, self.alive, self.returncode) == (other.pid, other.alive, other.returncode)

    def __hash__(self):
        return hash((self.pid, self.alive, self.returncode))


class JavaProcessBuilder:
    """Python stand-in for java.lang.ProcessBuilder: command list, working directory, redirect flag."""
    def __init__(self, command=None, directory=None, redirect_error_stream=False):
        self.command = command or []
        self.directory = directory
        self.redirect_error_stream = redirect_error_stream

    def __eq__(self, other):
        return isinstance(other, JavaProcessBuilder) and (self.command, self.directory, self.redirect_error_stream) == (other.command, other.directory, other.redirect_error_stream)


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
    "java.text.DecimalFormat": "str",
    "java.text.NumberFormat": "str",
    "java.text.SimpleDateFormat": "str",
    "java.text.Format": "str",
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
    "java.lang.Appendable": "io.StringIO",
    # Java IO/NIO, process, concurrency and utility types serialized by CustomToStringConverter (fallbacks only)
    "java.nio.file.Path": "pathlib.Path",
    "sun.nio.fs.UnixPath": "pathlib.Path",
    "sun.nio.fs.WindowsPath": "pathlib.Path",
    "java.nio.charset.Charset": "str",
    "java.nio.ByteBuffer": "io.BytesIO",
    "java.nio.HeapByteBuffer": "io.BytesIO",
    "java.nio.DirectByteBuffer": "io.BytesIO",
    "java.nio.IntBuffer": "list",
    "java.nio.LongBuffer": "list",
    "java.nio.ShortBuffer": "list",
    "java.nio.FloatBuffer": "list",
    "java.nio.DoubleBuffer": "list",
    "java.nio.Buffer": "list",
    "java.io.CharArrayReader": "io.StringIO",
    "java.io.CharArrayWriter": "io.StringIO",
    "java.io.BufferedWriter": "io.StringIO",
    "java.io.FilterReader": "io.StringIO",
    "java.io.PushbackReader": "io.StringIO",
    "java.io.FilterWriter": "io.StringIO",
    "java.io.LineNumberReader": "io.BufferedReader",
    "java.io.FileReader": "io.TextIOWrapper",
    "java.io.FileWriter": "io.TextIOWrapper",
    "java.io.Reader": "io.StringIO",
    "java.io.Writer": "io.StringIO",
    "java.io.DataInputStream": "io.BufferedReader",
    "java.io.PushbackInputStream": "io.BufferedReader",
    "java.io.SequenceInputStream": "io.BufferedReader",
    "java.io.ObjectInputStream": "io.BufferedReader",
    "java.io.DataOutputStream": "io.BufferedWriter",
    "java.io.ObjectOutputStream": "io.BufferedWriter",
    "java.lang.ProcessImpl$ProcessPipeInputStream": "io.BufferedReader",
    "java.lang.ProcessImpl$ProcessPipeOutputStream": "io.BufferedWriter",
    "java.lang.UNIXProcess$ProcessPipeInputStream": "io.BufferedReader",
    "java.lang.UNIXProcess$ProcessPipeOutputStream": "io.BufferedWriter",
    "java.io.RandomAccessFile": "io.FileIO",
    "java.io.FileDescriptor": "int",
    "java.lang.Process": "JavaProcess",
    "java.lang.ProcessImpl": "JavaProcess",
    "java.lang.UNIXProcess": "JavaProcess",
    "java.lang.ProcessBuilder": "JavaProcessBuilder",
    "java.lang.Thread": "threading.Thread",
    "java.util.concurrent.atomic.AtomicLong": "int",
    "java.util.concurrent.atomic.AtomicBoolean": "bool",
    "java.util.concurrent.atomic.AtomicReference": "atomic_reference",
    "java.util.concurrent.locks.ReentrantLock": "threading.Lock",
    "java.util.concurrent.locks.ReentrantReadWriteLock": "threading.Lock",
    "java.util.concurrent.locks.ReentrantReadWriteLock$ReadLock": "threading.Lock",
    "java.util.concurrent.locks.ReentrantReadWriteLock$WriteLock": "threading.Lock",
    "java.util.Optional": "optional",
    "java.util.Map$Entry": "map_entry",
    "java.util.AbstractMap$SimpleEntry": "map_entry",
    "java.util.AbstractMap$SimpleImmutableEntry": "map_entry",
    "java.util.zip.Adler32": "CRC32",
    "java.util.zip.Checksum": "CRC32",
    "java.util.UUID": "str",
    "java.lang.Runnable": "typing.Callable",
} 

# ---------------------------------------------------------------------------------------------------------------------
# Context-aware type resolution.
#
# The translation pipeline produces, per project, a context-aware type map (CTM) at
#   data/type_resolution/<project>/type_mapping.json  :  { "<Java source type>": [ {translated_type, imports, reasoning}, ... ] }
# whose keys are source-level type names (e.g. "List<String>", "ByteArrayOutputStream", "Map<String, Option>") and whose
# values are the Python types the LLM resolved for each context in which the type occurs.  Deserialization used to ignore
# this map and rely only on the hard-coded `type_map` below.  The CTM is consulted first; the hard-coded map is used
# only as a fallback when the CTM has no usable entry for a type, i.e. when it resolves to nothing, to "object"/"Any", to a
# type that cannot be loaded, or to a Python type whose constructor does not match the serialized payload shape.
#
# Configuration (all optional):
#   MOCKINGBIRD_TYPE_MAP           explicit path to a type_mapping.json
#   MOCKINGBIRD_PROJECT            project name (otherwise inferred from the working directory)
#   MOCKINGBIRD_ROOT               MockingBird repository root (otherwise inferred from the working directory)
#   MOCKINGBIRD_TYPE_MAP_DEBUG=1   print every resolution decision
#   MOCKINGBIRD_TYPE_MAP_LOG=path  append one JSON line per resolution decision (used by the pipeline monitor)
# ---------------------------------------------------------------------------------------------------------------------
import json as _json
import collections as _collections

_UNUSABLE_TRANSLATIONS = {"", "object", "Object", "typing.Any", "Any", "any", "None", "NoneType", "null", "void"}

# Python constructor categories that convert_to_python() knows how to build from the serialized Java payload.
_SUPPORTED_CATEGORIES = {
    "str", "int", "float", "numbers.Number", "bool", "tuple", "list", "dict_keys", "dict_values", "set", "dict", "bytearray",
    "Exception", "CRC32", "PeekableIterator", "urllib.parse.ParseResult", "io.BytesIO", "io.StringIO", "logging.Logger",
    "re.Match", "io.BufferedReader", "io.BufferedWriter", "io.FileIO", "io.TextIOWrapper", "type", "pathlib.Path",
    "datetime.timezone", "zoneinfo.ZoneInfo", "datetime.datetime", "datetime.timedelta", "threading.Thread",
    "typing.Callable", "None", "JavaProcess", "JavaProcessBuilder", "threading.Lock", "int_list", "optional", "atomic_reference", "map_entry",
}

# Which categories can be built from which serialized payload shapes (keys emitted by CustomToStringConverter).
_SHAPE_COMPATIBILITY = [
    (("collection_details",), {"PeekableIterator"}),
    (("keys", "values"), {"dict", "PeekableIterator"}),
    (("collection_elements",), {"list", "tuple", "set", "dict_keys", "dict_values", "int_list", "PeekableIterator"}),
    (("buffer_elements",), {"bytearray", "io.BytesIO"}),
    (("byte_array",), {"io.BytesIO", "bytearray"}),
    (("sink_details",), {"io.BytesIO"}),
    (("stream_type",), {"io.BufferedReader", "io.BufferedWriter"}),
    (("content",), {"io.StringIO", "io.BufferedReader", "io.TextIOWrapper"}),
    (("encoding",), {"io.TextIOWrapper", "io.BufferedReader", "io.StringIO"}),
    (("file_path",), {"io.FileIO", "pathlib.Path"}),
    (("timestamp",), {"datetime.datetime"}),
    (("instant",), {"datetime.datetime"}),
    (("seconds",), {"datetime.timedelta"}),
    (("id", "offset"), {"datetime.timezone", "zoneinfo.ZoneInfo"}),
    (("pattern_str",), {"re.Match"}),
    (("pattern",), {"str"}),
    (("throwable_type",), {"Exception"}),
    (("pid",), {"JavaProcess"}),
    (("command", "redirect_error_stream"), {"JavaProcessBuilder"}),
    (("present", "referent"), {"optional"}),
    (("referent",), {"atomic_reference"}),
    (("key", "entry_value"), {"map_entry"}),
    (("lock_class",), {"threading.Lock"}),
    (("thread_class",), {"threading.Thread"}),
    (("ctor_declaring_class",), {"typing.Callable"}),
    (("method_declaring_class",), {"typing.Callable"}),
    (("enum_name",), None),      # enums: resolved through the src.* class, never through the CTM
    (("instance_fields",), None),  # application objects: resolved through the src.* class, never through the CTM
]
_SCALAR_CATEGORIES = {"str", "int", "float", "numbers.Number", "bool", "pathlib.Path", "type", "urllib.parse.ParseResult", "CRC32", "typing.Callable", "None", "threading.Thread", "threading.Lock"}

# JDK type hierarchy (Java facts, not Java->Python mapping): runtime class -> source-level supertypes to try in the CTM,
# most specific first.  Used because the serialized payload carries the runtime class while CTM keys are declared types.
_JDK_SUPERTYPES = {
    "java.util.ArrayList": ["List", "Collection", "Iterable"], "java.util.LinkedList": ["List", "Deque", "Queue", "Collection"],
    "java.util.Vector": ["List", "Collection"], "java.util.Stack": ["Stack", "List", "Collection"],
    "java.util.Arrays$ArrayList": ["List", "Collection"], "java.util.Collections$UnmodifiableRandomAccessList": ["List", "Collection"],
    "java.util.Collections$UnmodifiableList": ["List", "Collection"], "java.util.Collections$SingletonList": ["List", "Collection"],
    "java.util.Collections$EmptyList": ["List", "Collection"], "java.util.RandomAccessSubList": ["List"], "java.util.ArrayList$SubList": ["List"],
    "java.util.ImmutableCollections$ListN": ["List", "Collection"], "java.util.ImmutableCollections$List12": ["List", "Collection"],
    "java.util.concurrent.CopyOnWriteArrayList": ["List", "Collection"], "java.util.ArrayDeque": ["Deque", "Queue", "Collection"],
    "java.util.PriorityQueue": ["PriorityQueue", "Queue", "Collection"], "java.util.concurrent.LinkedBlockingQueue": ["BlockingQueue", "Queue", "Collection"],
    "java.util.concurrent.LinkedBlockingDeque": ["BlockingDeque", "Deque", "Queue", "Collection"],
    "java.util.HashMap": ["Map"], "java.util.LinkedHashMap": ["Map"], "java.util.TreeMap": ["SortedMap", "NavigableMap", "Map"],
    "java.util.Hashtable": ["Map"], "java.util.IdentityHashMap": ["Map"], "java.util.WeakHashMap": ["Map"], "java.util.EnumMap": ["Map"],
    "java.util.concurrent.ConcurrentHashMap": ["ConcurrentMap", "Map"], "java.util.Collections$UnmodifiableMap": ["Map"],
    "java.util.Collections$EmptyMap": ["Map"], "java.util.Collections$SingletonMap": ["Map"], "java.util.ImmutableCollections$MapN": ["Map"],
    "java.util.ImmutableCollections$Map1": ["Map"], "java.util.Properties": ["Properties", "Map"],
    "java.util.HashSet": ["Set", "Collection"], "java.util.LinkedHashSet": ["Set", "Collection"], "java.util.TreeSet": ["SortedSet", "NavigableSet", "Set", "Collection"],
    "java.util.EnumSet": ["EnumSet", "Set"], "java.util.RegularEnumSet": ["EnumSet", "Set"], "java.util.JumboEnumSet": ["EnumSet", "Set"],
    "java.util.Collections$UnmodifiableSet": ["Set", "Collection"], "java.util.Collections$EmptySet": ["Set", "Collection"],
    "java.util.Collections$SingletonSet": ["Set", "Collection"], "java.util.ImmutableCollections$SetN": ["Set", "Collection"],
    "java.util.ImmutableCollections$Set12": ["Set", "Collection"], "java.util.HashMap$KeySet": ["Set", "Collection"],
    "java.util.LinkedHashMap$LinkedKeySet": ["Set", "Collection"], "java.util.HashMap$Values": ["Collection"],
    "java.util.LinkedHashMap$LinkedValues": ["Collection"], "java.util.Collections$UnmodifiableCollection": ["Collection"],
    "java.util.ArrayList$Itr": ["Iterator"], "java.util.ArrayList$ListItr": ["ListIterator", "Iterator"],
    "java.util.LinkedList$ListItr": ["ListIterator", "Iterator"], "java.util.HashMap$KeyIterator": ["Iterator"],
    "java.util.HashMap$ValueIterator": ["Iterator"], "java.util.HashMap$EntryIterator": ["Iterator"],
    "java.util.LinkedHashMap$LinkedKeyIterator": ["Iterator"], "java.util.LinkedHashMap$LinkedValueIterator": ["Iterator"],
    "java.util.LinkedHashMap$LinkedEntryIterator": ["Iterator"], "java.util.Collections$UnmodifiableCollection$1": ["Iterator"],
    "java.util.Iterator": ["Iterator"], "java.util.ListIterator": ["ListIterator", "Iterator"], "java.util.Enumeration": ["Enumeration"],
    "java.util.stream.ReferencePipeline$Head": ["Stream"], "java.util.stream.ReferencePipeline$2": ["Stream"], "java.util.stream.ReferencePipeline$3": ["Stream"],
    "java.lang.StringBuilder": ["StringBuilder", "CharSequence", "Appendable"], "java.lang.StringBuffer": ["StringBuffer", "CharSequence", "Appendable"],
    "java.lang.String": ["String", "CharSequence"], "java.lang.Integer": ["Integer", "Number"], "java.lang.Long": ["Long", "Number"],
    "java.lang.Short": ["Short", "Number"], "java.lang.Byte": ["Byte", "Number"], "java.lang.Double": ["Double", "Number"],
    "java.lang.Float": ["Float", "Number"], "java.math.BigInteger": ["BigInteger", "Number"], "java.math.BigDecimal": ["BigDecimal", "Number"],
    "java.util.concurrent.atomic.AtomicInteger": ["AtomicInteger", "Number"], "java.util.concurrent.atomic.AtomicLong": ["AtomicLong", "Number"],
    "java.lang.Boolean": ["Boolean"], "java.lang.Character": ["Character"],
    "java.io.ByteArrayInputStream": ["ByteArrayInputStream", "InputStream"], "java.io.FileInputStream": ["FileInputStream", "InputStream"],
    "java.io.BufferedInputStream": ["BufferedInputStream", "FilterInputStream", "InputStream"], "java.io.DataInputStream": ["DataInputStream", "FilterInputStream", "InputStream"],
    "java.io.PushbackInputStream": ["PushbackInputStream", "FilterInputStream", "InputStream"], "java.io.FilterInputStream": ["FilterInputStream", "InputStream"],
    "java.io.PipedInputStream": ["PipedInputStream", "InputStream"], "java.io.SequenceInputStream": ["SequenceInputStream", "InputStream"],
    "java.io.ObjectInputStream": ["ObjectInputStream", "InputStream"], "java.lang.ProcessImpl$ProcessPipeInputStream": ["BufferedInputStream", "InputStream"],
    "java.io.ByteArrayOutputStream": ["ByteArrayOutputStream", "OutputStream"], "java.io.FileOutputStream": ["FileOutputStream", "OutputStream"],
    "java.io.BufferedOutputStream": ["BufferedOutputStream", "FilterOutputStream", "OutputStream"], "java.io.DataOutputStream": ["DataOutputStream", "FilterOutputStream", "OutputStream"],
    "java.io.FilterOutputStream": ["FilterOutputStream", "OutputStream"], "java.io.PipedOutputStream": ["PipedOutputStream", "OutputStream"],
    "java.io.PrintStream": ["PrintStream", "FilterOutputStream", "OutputStream"], "java.io.ObjectOutputStream": ["ObjectOutputStream", "OutputStream"],
    "java.lang.ProcessImpl$ProcessPipeOutputStream": ["BufferedOutputStream", "OutputStream"],
    "java.io.StringReader": ["StringReader", "Reader"], "java.io.CharArrayReader": ["CharArrayReader", "Reader"],
    "java.io.BufferedReader": ["BufferedReader", "Reader"], "java.io.LineNumberReader": ["LineNumberReader", "BufferedReader", "Reader"],
    "java.io.InputStreamReader": ["InputStreamReader", "Reader"], "java.io.FileReader": ["FileReader", "InputStreamReader", "Reader"],
    "java.io.PushbackReader": ["PushbackReader", "FilterReader", "Reader"], "java.io.FilterReader": ["FilterReader", "Reader"], "java.io.PipedReader": ["PipedReader", "Reader"],
    "java.io.StringWriter": ["StringWriter", "Writer", "Appendable"], "java.io.CharArrayWriter": ["CharArrayWriter", "Writer", "Appendable"],
    "java.io.BufferedWriter": ["BufferedWriter", "Writer", "Appendable"], "java.io.OutputStreamWriter": ["OutputStreamWriter", "Writer", "Appendable"],
    "java.io.FileWriter": ["FileWriter", "OutputStreamWriter", "Writer", "Appendable"], "java.io.PrintWriter": ["PrintWriter", "Writer", "Appendable"],
    "java.io.FilterWriter": ["FilterWriter", "Writer", "Appendable"], "java.io.PipedWriter": ["PipedWriter", "Writer", "Appendable"],
    "java.io.File": ["File"], "sun.nio.fs.UnixPath": ["Path"], "sun.nio.fs.WindowsPath": ["Path"], "java.nio.file.Path": ["Path"],
    "java.nio.HeapByteBuffer": ["ByteBuffer", "Buffer"], "java.nio.DirectByteBuffer": ["ByteBuffer", "Buffer"], "java.nio.HeapByteBufferR": ["ByteBuffer", "Buffer"],
    "java.nio.HeapCharBuffer": ["CharBuffer", "Buffer"], "java.nio.HeapIntBuffer": ["IntBuffer", "Buffer"], "java.nio.ByteBufferAsIntBufferL": ["IntBuffer", "Buffer"],
    "java.nio.ByteBufferAsIntBufferB": ["IntBuffer", "Buffer"], "java.nio.HeapLongBuffer": ["LongBuffer", "Buffer"], "java.nio.HeapShortBuffer": ["ShortBuffer", "Buffer"],
    "java.nio.HeapFloatBuffer": ["FloatBuffer", "Buffer"], "java.nio.HeapDoubleBuffer": ["DoubleBuffer", "Buffer"],
    "sun.nio.cs.UTF_8": ["Charset"], "sun.nio.cs.ISO_8859_1": ["Charset"], "sun.nio.cs.US_ASCII": ["Charset"], "sun.nio.cs.UTF_16": ["Charset"],
    "java.lang.ProcessImpl": ["Process"], "java.lang.UNIXProcess": ["Process"], "java.lang.Thread": ["Thread", "Runnable"],
    "java.util.concurrent.Executors$DefaultThreadFactory": ["ThreadFactory"], "java.util.concurrent.locks.ReentrantLock": ["ReentrantLock", "Lock"],
    "java.util.zip.CRC32": ["CRC32", "Checksum"], "java.util.zip.Adler32": ["Adler32", "Checksum"],
    "java.util.regex.Pattern": ["Pattern"], "java.util.regex.Matcher": ["Matcher"], "java.util.Scanner": ["Scanner", "Iterator"],
    "java.net.URL": ["URL"], "java.net.URI": ["URI"], "java.util.Date": ["Date"], "java.util.GregorianCalendar": ["Calendar"],
    "java.util.Locale": ["Locale"], "java.util.BitSet": ["BitSet"], "java.util.Optional": ["Optional"],
}

_ctm_state = {"loaded": False, "path": None, "project": None, "index": {}, "raw_keys": 0, "stats": _collections.Counter()}


def _ctm_debug(msg):
    if os.environ.get("MOCKINGBIRD_TYPE_MAP_DEBUG"):
        print(f"[type-map] {msg}", flush=True)


def _infer_project_and_root():
    """Infer (project, repo_root) from env or from the working directory layout used by the pipeline."""
    project = os.environ.get("MOCKINGBIRD_PROJECT")
    root = os.environ.get("MOCKINGBIRD_ROOT")
    cwd = os.path.abspath(os.getcwd())
    parts = cwd.split(os.sep)
    if "data" in parts:
        i = parts.index("data")
        root = root or os.sep.join(parts[:i]) or os.sep
        if project is None and i + 1 < len(parts):
            if parts[i + 1] == "recomposed_projects" and i + 4 < len(parts):
                project = parts[i + 4]
            elif parts[i + 1] == "mock_tests" and i + 2 < len(parts):
                project = parts[i + 2]
    if project is None:
        for p in reversed(parts):
            if p.endswith("-python"):
                project = p[: -len("-python")]
                break
    if root is None and "src" in parts:
        root = os.sep.join(parts[: parts.index("src")]) or os.sep
    return project, root


def _candidate_type_map_paths():
    explicit = os.environ.get("MOCKINGBIRD_TYPE_MAP")
    if explicit:
        yield explicit
    project, root = _infer_project_and_root()
    if project:
        roots = [r for r in [root, os.getcwd()] if r]
        for r in roots:
            yield os.path.join(r, "data", "type_resolution", project, "type_mapping.json")
        # walk up from the working directory as a last resort
        cur = os.path.abspath(os.getcwd())
        for _ in range(8):
            yield os.path.join(cur, "data", "type_resolution", project, "type_mapping.json")
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent


def _strip_generics_and_arrays(type_str):
    """'java.util.List<String>[]' -> ('List', True); 'Map<String, List<Integer>>' -> ('Map', False)."""
    s = type_str.strip()
    is_array = False
    while s.endswith("[]"):
        s = s[:-2].strip(); is_array = True
    depth = 0; out = []
    for ch in s:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif depth == 0:
            out.append(ch)
    base = "".join(out).strip()
    base = base.split(".")[-1] if "." in base else base
    return base, is_array


_TYPING_CATEGORY = [
    (re.compile(r"^(typing\.)?(List|MutableSequence|Sequence|Iterable|Collection|Deque|Queue)\b"), "list"),
    (re.compile(r"^(collections\.)?deque\b"), "list"),
    (re.compile(r"^(typing\.)?(Dict|Mapping|MutableMapping|DefaultDict|OrderedDict|Counter)\b"), "dict"),
    (re.compile(r"^(collections\.)?(OrderedDict|defaultdict|Counter)\b"), "dict"),
    (re.compile(r"^(typing\.)?(Set|MutableSet|FrozenSet|AbstractSet)\b"), "set"),
    (re.compile(r"^(typing\.)?Tuple\b"), "tuple"),
    (re.compile(r"^(typing\.|collections\.abc\.)?(Iterator|Generator)\b"), "PeekableIterator"),
    (re.compile(r"^(typing\.)?Callable\b"), "typing.Callable"),
    (re.compile(r"^(typing\.)?Type\b"), "type"),
    (re.compile(r"^(typing\.)?(Text|AnyStr)\b"), "str"),
    (re.compile(r"^(typing\.)?(BinaryIO|IO)\b"), "io.BytesIO"),
    (re.compile(r"^(typing\.)?TextIO\b"), "io.TextIOWrapper"),
]
_ALIAS_CATEGORY = {
    "list": "list", "dict": "dict", "set": "set", "frozenset": "set", "tuple": "tuple", "str": "str", "int": "int", "float": "float",
    "bool": "bool", "bytes": "bytearray", "bytearray": "bytearray", "memoryview": "bytearray", "complex": "float", "decimal.Decimal": "float", "Decimal": "float",
    "numbers.Number": "numbers.Number", "Number": "numbers.Number", "object": None, "None": None, "type": "type",
    "pathlib.Path": "pathlib.Path", "Path": "pathlib.Path", "pathlib.PurePath": "pathlib.Path", "os.PathLike": "pathlib.Path",
    "datetime.datetime": "datetime.datetime", "datetime": "datetime.datetime", "datetime.date": "datetime.datetime", "date": "datetime.datetime",
    "datetime.timedelta": "datetime.timedelta", "timedelta": "datetime.timedelta", "datetime.timezone": "datetime.timezone", "timezone": "datetime.timezone",
    "zoneinfo.ZoneInfo": "zoneinfo.ZoneInfo", "ZoneInfo": "zoneinfo.ZoneInfo",
    "io.BytesIO": "io.BytesIO", "BytesIO": "io.BytesIO", "io.StringIO": "io.StringIO", "StringIO": "io.StringIO",
    "io.BufferedReader": "io.BufferedReader", "BufferedReader": "io.BufferedReader", "io.BufferedWriter": "io.BufferedWriter", "BufferedWriter": "io.BufferedWriter",
    "io.TextIOWrapper": "io.TextIOWrapper", "TextIOWrapper": "io.TextIOWrapper", "io.FileIO": "io.FileIO", "FileIO": "io.FileIO",
    "io.IOBase": "io.BytesIO", "IOBase": "io.BytesIO", "io.RawIOBase": "io.BytesIO", "io.BufferedIOBase": "io.BytesIO", "io.TextIOBase": "io.StringIO",
    "urllib.parse.ParseResult": "urllib.parse.ParseResult", "ParseResult": "urllib.parse.ParseResult",
    "re.Match": "re.Match", "Match": "re.Match", "re.Pattern": "str", "Pattern": "str",
    "threading.Thread": "threading.Thread", "Thread": "threading.Thread", "threading.Lock": "threading.Lock", "threading.RLock": "threading.Lock", "Lock": "threading.Lock", "RLock": "threading.Lock",
    "logging.Logger": "logging.Logger", "Logger": "logging.Logger", "subprocess.Popen": "JavaProcess", "Popen": "JavaProcess",
    "PeekableIterator": "PeekableIterator", "CRC32": "CRC32", "zlib.crc32": "CRC32",
    "Exception": "Exception", "BaseException": "Exception",
}


def _normalize_translated_type(translated):
    """Reduce an LLM-produced Python type string to a deserialization category, or None if it is unusable."""
    if translated is None:
        return None
    t = str(translated).strip().strip("`'\"").strip()
    if not t or t in _UNUSABLE_TRANSLATIONS:
        return None
    t = t.split("\n")[-1].strip()
    if t.startswith("Optional[") or t.startswith("typing.Optional["):
        t = t[t.index("[") + 1: -1].strip()
    if t.startswith("Union[") or t.startswith("typing.Union["):
        inner = t[t.index("[") + 1: -1]
        t = [x.strip() for x in inner.split(",") if x.strip() not in ("None", "NoneType")][0] if inner else t
    if t in _UNUSABLE_TRANSLATIONS:
        return None
    base = t.split("[")[0].strip()
    if base in _ALIAS_CATEGORY:
        return _ALIAS_CATEGORY[base]
    for pattern, category in _TYPING_CATEGORY:
        if pattern.match(t):
            return category
    if base.lower() in _ALIAS_CATEGORY:
        return _ALIAS_CATEGORY[base.lower()]
    # builtin exceptions keep their own name (convert_to_python / create_python_object handle them)
    if hasattr(builtins, base) and isinstance(getattr(builtins, base), type) and issubclass(getattr(builtins, base), BaseException):
        return base
    # application classes translated by the pipeline (fully qualified or bare name present in the loaded modules)
    if base.startswith("src."):
        return base
    for key in list(globals().keys()):
        if key.startswith("src.") and (key.endswith("." + base) or key == base):
            return key
    return None


def _load_context_type_map():
    if _ctm_state["loaded"]:
        return
    _ctm_state["loaded"] = True
    project, _root = _infer_project_and_root()
    _ctm_state["project"] = project
    for path in _candidate_type_map_paths():
        if path and os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    raw = _json.load(f)
            except Exception as e:
                _ctm_debug(f"could not read {path}: {e}")
                continue
            index = _collections.defaultdict(list)
            for key, entries in raw.items():
                if not entries:
                    continue
                base, is_array = _strip_generics_and_arrays(key)
                for entry in entries:
                    cat = _normalize_translated_type((entry or {}).get("translated_type"))
                    if cat is None:
                        continue
                    if is_array:
                        index[base + "[]"].append(cat)
                    else:
                        index[base].append(cat)
                        index[key.strip()].append(cat)
            _ctm_state["index"] = dict(index)
            _ctm_state["path"] = path
            _ctm_state["raw_keys"] = len(raw)
            _ctm_debug(f"loaded context-aware type map {path}: {len(raw)} source types, {len(index)} usable keys")
            return
    _ctm_debug(f"no context-aware type map found (project={project}); using the fixed mapping only")


_BOXED_TO_PRIMITIVE = {
    "java.lang.Byte": ["byte"], "java.lang.Character": ["char"], "java.lang.Short": ["short"], "java.lang.Integer": ["int"],
    "java.lang.Long": ["long"], "java.lang.Float": ["float"], "java.lang.Double": ["double"], "java.lang.Boolean": ["boolean"],
}


def _ctm_candidates(class_name):
    """Source-level names to look up for a runtime class name, most specific first."""
    cands = [class_name]
    simple = class_name.split(".")[-1]
    if "$" in simple:
        outer, inner = simple.split("$")[0], simple.split("$")[-1]
        cands += [inner, f"{outer}.{inner}", outer]
    else:
        cands.append(simple)
    if class_name.endswith("[]"):
        base, _ = _strip_generics_and_arrays(class_name)
        cands += [base + "[]"]
    cands += _JDK_SUPERTYPES.get(class_name, [])
    # boxed JDK values arrive with their wrapper class name, while source-level signatures (the context map's keys) mostly
    # use the primitive: look the primitive up as well
    cands += _BOXED_TO_PRIMITIVE.get(class_name, [])
    seen = set(); out = []
    for c in cands:
        if c and c not in seen:
            seen.add(c); out.append(c)
    return out


def _payload_compatible(category, json_obj):
    """True if convert_to_python() can build `category` from the serialized payload `json_obj`."""
    if json_obj is None:
        return True
    keys = set(json_obj.keys())
    for shape_keys, allowed in _SHAPE_COMPATIBILITY:
        if all(k in keys for k in shape_keys):
            if allowed is None:
                return False
            return category in allowed
    if "value" in keys:
        if category in _SCALAR_CATEGORIES:
            return True
        if category in ("io.StringIO", "io.BufferedReader") and isinstance(json_obj.get("value"), str):
            return True   # StringReader / StringWriter payloads: {"value": content, "position": n}
        return False
    return category in _SUPPORTED_CATEGORIES


def _is_loadable_category(category):
    if category in _SUPPORTED_CATEGORIES:
        return True
    if category.startswith("src."):
        return category in globals()
    if hasattr(builtins, category):
        return True
    try:
        module_name, attr = category.rsplit(".", 1)
        return hasattr(importlib.import_module(module_name), attr)
    except Exception:
        return False


def resolve_from_context_type_map(class_name, json_obj=None):
    """Return (category, matched_key) from the project's context-aware type map, or (None, None) if unusable."""
    _load_context_type_map()
    index = _ctm_state["index"]
    if not index:
        return None, None
    for cand in _ctm_candidates(class_name):
        cats = index.get(cand)
        if not cats:
            continue
        # majority vote across the contexts in which the type occurred; ties favour the most specific (first) entry
        ranked = [c for c, _n in _collections.Counter(cats).most_common()]
        for cat in ranked:
            if cat is None or cat in _UNUSABLE_TRANSLATIONS:
                continue
            if not _is_loadable_category(cat):
                _ctm_debug(f"{class_name}: CTM[{cand}] -> {cat} is not loadable; trying next")
                continue
            if not _payload_compatible(cat, json_obj):
                _ctm_debug(f"{class_name}: CTM[{cand}] -> {cat} does not match the payload shape; trying next")
                continue
            return cat, cand
    return None, None


def _record_resolution(class_name, category, source, matched_key=None):
    _ctm_state["stats"][source] += 1
    log_path = os.environ.get("MOCKINGBIRD_TYPE_MAP_LOG")
    if log_path:
        try:
            with open(log_path, "a") as f:
                f.write(_json.dumps({"project": _ctm_state["project"], "java_type": class_name, "python_type": category, "source": source, "ctm_key": matched_key}) + "\n")
        except Exception:
            pass
    _ctm_debug(f"{class_name} -> {category} [{source}{(' via ' + matched_key) if matched_key else ''}]")


def type_resolution_stats():
    """Counts of how types were resolved in this process: context_type_map vs fixed_fallback vs application_class."""
    return dict(_ctm_state["stats"])


def retrieve_from_type_map(class_name, default, json_obj=None):
    """
    Resolve a Java runtime class name to the Python type/category used for deserialization.
    Order: application classes (src.*) -> context-aware type map of the project -> fixed fallback mapping.
    """
    if class_name.startswith("src."):
        if "$" in class_name:
            return class_name.replace("$", ".")
        else:
            last = class_name.split(".")[-1]
            return f"{class_name}.{last}"
    category, matched_key = resolve_from_context_type_map(class_name, json_obj)
    if category is not None:
        _record_resolution(class_name, category, "context_type_map", matched_key)
        return category
    fallback = type_map.get(class_name, default)
    _record_resolution(class_name, fallback, "fixed_fallback" if class_name in type_map else "default")
    return fallback

class _ExceptionFamilyMeta(type):
    """A Java exception whose Python counterpart is not unique (a NullPointerException surfaces as TypeError or
    AttributeError depending on how the null is used) is deserialized as a subclass of the mapped type that also
    matches the other members of its family in isinstance/issubclass checks, so assertRaises(type(e)) accepts any of them."""
    def __instancecheck__(cls, instance):
        return isinstance(instance, cls.family)

    def __subclasscheck__(cls, subclass):
        return issubclass(subclass, cls.family)


_EXCEPTION_FAMILIES = {
    "java.lang.NullPointerException": (TypeError, AttributeError),
    "java.lang.ClassCastException": (TypeError, AttributeError),
    "java.util.NoSuchElementException": (StopIteration, LookupError),
}
_family_class_cache = {}


def _family_exception_class(base, family):
    key = (base, family)
    if key not in _family_class_cache:
        _family_class_cache[key] = _ExceptionFamilyMeta(base.__name__, (base,), {"family": family})
    return _family_class_cache[key]


class JavaObject:
    """stand-in for a bare java.lang.Object instance (no state): equal to any other bare object"""
    def __eq__(self, other):
        return isinstance(other, JavaObject)

    def __hash__(self):
        return 0

    def __repr__(self):
        return "JavaObject()"


_ADAPTER_BASE_NAMES = ("ReentrantLockAdapter", "TimerTaskAdapter")


def _adapter_bases(obj):
    return [b for b in type(obj).__mro__ if b.__name__ in _ADAPTER_BASE_NAMES]


def _detach_raw(stream):
    """Return the innermost raw stream of a TextIOWrapper/BufferedReader/BufferedWriter chain. The wrappers are detached
    rather than dereferenced: a wrapper that is merely garbage-collected closes the stream it wraps."""
    while hasattr(stream, "detach") and not isinstance(stream, (BytesIO, StringIO)):
        try:
            stream = stream.detach()
        except (ValueError, AttributeError):
            break
    return stream


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

    note = json_obj.get("special_note")
    if note in ("decimal_format", "date_format", "text_format"):
        return json_obj.get("pattern") if json_obj.get("pattern") is not None else json_obj.get("value")
    if note == "plain_object":
        return JavaObject()

    python_type = retrieve_from_type_map(java_type, java_type, json_obj)

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
        if "byte_array" in json_obj:   # java.nio.ByteBuffer serialized as a byte[] + size/position
            raw = convert_to_python(json_obj.get("byte_array"), force_new_object=True) or []
            size = int(json_obj.get("size", len(raw)))
            elements = []
            ba = bytearray(bytes([int(x) & 0xFF for x in raw[:size]]))
        else:
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
        throwable_type = json_obj.get("throwable_type", "java.lang.Throwable")
        exception_name = retrieve_from_type_map(throwable_type, "Exception")
        message = json_obj.get("message", None)
        exception_cls = getattr(builtins, exception_name, None)
        if isinstance(exception_cls, type) and issubclass(exception_cls, BaseException):
            family = _EXCEPTION_FAMILIES.get(throwable_type)
            if family is not None and issubclass(exception_cls, family):
                return _family_exception_class(exception_cls, family)(message)
            return exception_cls(message)
        app_cls = globals().get(exception_name)
        if isinstance(app_cls, type) and issubclass(app_cls, BaseException):
            # translated application exception: its __init__ may require project-specific arguments, so build the instance
            # without calling it (same approach as create_python_object) and carry the recorded message
            try:
                obj = Exception.__new__(app_cls)
            except TypeError:
                obj = app_cls.__new__(app_cls)
            obj.args = (message,) if message is not None else ()
            return obj
        return Exception(message)
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
            elif json_obj.get("special_note") == "System.in":
                return sys.stdin
            elif json_obj.get("special_note") == "byte_stream" and json_obj.get("byte_stream") is not None:
                return convert_to_python(json_obj.get("byte_stream"))
            elif json_obj.get("special_note") == "file_stream" and json_obj.get("file_stream") is not None:
                return convert_to_python(json_obj.get("file_stream"))
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
            if json_obj.get("stream_type") in ("byte_stream", "sequence"):
                byte_stream = convert_to_python(json_obj.get("stream_details"))
                if isinstance(byte_stream, (BufferedReader, TextIOWrapper)):
                    byte_stream = _detach_raw(byte_stream)
                if not isinstance(byte_stream, BytesIO):
                    byte_stream = BytesIO(byte_stream.read() if hasattr(byte_stream, "read") else b"")
                content_bytes = byte_stream.getvalue()
                position = byte_stream.tell()
            elif json_obj.get("stream_type") == "file_stream":
                obj = convert_to_python(json_obj.get("stream_details"))
                if isinstance(obj, BytesIO):
                    return BufferedReader(obj)
                return BufferedReader(_detach_raw(obj)) if hasattr(obj, "buffer") else obj
            else:
                return BufferedReader(BytesIO())
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
            if isinstance(byte_stream, (BufferedWriter, TextIOWrapper)):
                byte_stream = _detach_raw(byte_stream)
            if not isinstance(byte_stream, BytesIO):
                byte_stream = BytesIO()
            content_bytes = byte_stream.getvalue()
            position = byte_stream.tell()
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
            if isinstance(obj, BytesIO):
                return BufferedWriter(obj)
            return BufferedWriter(_detach_raw(obj)) if hasattr(obj, "buffer") else obj
        elif json_obj.get("special_note") == "System.out":
            return sys.stdout
        elif json_obj.get("special_note") == "System.err":
            return sys.stderr
        else:
            return BufferedWriter(BytesIO())
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
                underlying = _detach_raw(convert_to_python(json_obj.get("stream_details")))
            else:
                underlying = BytesIO()
        else:
            underlying = BytesIO()
        clazz = globals().get(python_type)
        obj = clazz.__new__(clazz)
        # the translated stream classes subclass io.BufferedReader (input streams) or io.BufferedWriter (output streams)
        (BufferedWriter if issubclass(clazz, BufferedWriter) else BufferedReader).__init__(obj, underlying)
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
        if file_path is None:
            # descriptor-backed Java stream (process pipe, System.in/out): no file to reopen; expose an empty buffer
            if json_obj.get("special_note") == "System.in":
                return TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
            empty = BytesIO()
            memory_address = json_obj.get("memory_address")
            if force_new_object or not memory_address:
                return empty
            reference_dict.setdefault(memory_address, empty)
            return reference_dict[memory_address]
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
        elif special_note == "System.out":
            textIOWrapper_obj = sys.stdout
        elif special_note == "System.err":
            textIOWrapper_obj = sys.stderr
        elif special_note == "byte_stream" and json_obj.get("byte_stream") is not None:
            textIOWrapper_obj = TextIOWrapper(convert_to_python(json_obj.get("byte_stream")), encoding=encoding)
        elif special_note == "file_stream" and json_obj.get("file_stream") is not None:
            textIOWrapper_obj = convert_to_python(json_obj.get("file_stream"))
        elif "content" in json_obj:
            textIOWrapper_obj = TextIOWrapper(BytesIO(str(json_obj.get("content", "")).encode(encoding or "utf-8")), encoding=encoding or "utf-8")
        else:
            textIOWrapper_obj = TextIOWrapper(BytesIO(), encoding=encoding or "utf-8")
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
        return Thread(target=None, name=json_obj.get("name"), args=(), kwargs=None, daemon=bool(json_obj.get("daemon", False)))
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
    elif python_type == 'JavaProcess':
        proc = JavaProcess(pid=json_obj.get("pid"), alive=bool(json_obj.get("alive", False)), exit_value=json_obj.get("exit_value"),
                           stdout=convert_to_python(json_obj["stdout"], force_new_object=True) if isinstance(json_obj.get("stdout"), dict) else None,
                           stderr=convert_to_python(json_obj["stderr"], force_new_object=True) if isinstance(json_obj.get("stderr"), dict) else None,
                           stdin=convert_to_python(json_obj["stdin"], force_new_object=True) if isinstance(json_obj.get("stdin"), dict) else None)
        memory_address = json_obj.get("memory_address")
        if force_new_object or not memory_address:
            return proc
        if memory_address in reference_dict and reference_dict[memory_address] is not None:
            reference_dict[memory_address].__dict__.update(proc.__dict__)
        else:
            reference_dict[memory_address] = proc
        return reference_dict[memory_address]
    elif python_type == 'JavaProcessBuilder':
        return JavaProcessBuilder(command=convert_to_python(json_obj.get("command", {"type": "java.util.ArrayList", "collection_elements": []}), force_new_object=True),
                                  directory=json_obj.get("directory"), redirect_error_stream=bool(json_obj.get("redirect_error_stream", False)))
    elif python_type == 'threading.Lock':
        import threading as _threading
        lock = _threading.RLock()
        if json_obj.get("locked"):
            lock.acquire(blocking=False)
        return lock
    elif python_type == 'optional':
        if not json_obj.get("present") or json_obj.get("referent") is None:
            return None
        return convert_to_python(json_obj.get("referent"), force_new_object=force_new_object)
    elif python_type == 'atomic_reference':
        referent = json_obj.get("referent")
        return convert_to_python(referent, force_new_object=force_new_object) if isinstance(referent, dict) else None
    elif python_type == 'map_entry':
        key = convert_to_python(json_obj["key"], force_new_object=force_new_object) if isinstance(json_obj.get("key"), dict) else None
        val = convert_to_python(json_obj["entry_value"], force_new_object=force_new_object) if isinstance(json_obj.get("entry_value"), dict) else None
        return (key, val)
    elif python_type == 'int_list':
        return [convert_to_python(e, force_new_object=force_new_object) for e in json_obj.get("collection_elements", [])]
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

class Mismatch:
    """Falsy result of recursive_equal() that explains the first difference found (path, reason, both values).

    Mock tests assert `self.assertTrue(recursive_equal(actual, expected))`; unittest prints the repr of a falsy value in the
    failure message, so the explanation reaches the translation feedback loop without changing the generated tests.
    """
    def __init__(self, path, reason, actual, expected):
        self.path = path or "<the compared value itself: return value, or the object/field named in the assertion>"; self.reason = reason; self.actual = actual; self.expected = expected

    @staticmethod
    def _show(v, limit=300):
        try:
            r = repr(v)
        except Exception as e:
            r = f"<unprintable {type(v).__name__}: {e}>"
        return r if len(r) <= limit else r[:limit] + f"... ({len(r)} chars)"

    def __bool__(self):
        return False

    def __repr__(self):
        return (f"MISMATCH at {self.path}: {self.reason}. Python side (translated code): {self._show(self.actual)} "
                f"[type {type(self.actual).__name__}]; Java side (recorded execution): {self._show(self.expected)} [type {type(self.expected).__name__}]")

    __str__ = __repr__


def _child(path, key):
    return f"{path}{key}" if path else key


def recursive_equal(obj1, obj2, _path=""):
    """
    Recursively checks equality of two Python objects by comparing their attributes and values.
    `obj1` is the value produced by the translated Python code, `obj2` the value recorded from the Java execution.
    Returns True, or a falsy Mismatch describing the first difference (its repr is the assertion message).
    """
    def fail(reason, a=obj1, b=obj2, path=_path):
        return Mismatch(path, reason, a, b)

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
        if obj1._name_ != obj2._name_:
            return fail(f"enum member differs ({obj1._name_!r} vs {obj2._name_!r})")
        return recursive_equal(obj1._value_, obj2._value_, _child(_path, "._value_"))
    if isinstance(obj1, Exception) and isinstance(obj2, Exception):
        if issubclass(type(obj1), type(obj2)) or issubclass(type(obj2), type(obj1)):
            return True # Skip strict message equivalence check
        else:
            return fail(f"exception types are unrelated ({type(obj1).__name__} vs {type(obj2).__name__})")
    if _adapter_bases(obj1) or _adapter_bases(obj2):
        return True
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
        return fail(f"integer values differ ({obj1} vs {obj2})")
    if isinstance(obj1, timedelta) and isinstance(obj2, timedelta):
        TOLERANCE_SECONDS = 1e-6  # allow 1 microsecond difference (avoid numerical issues)
        if abs(obj1.total_seconds() - obj2.total_seconds()) < TOLERANCE_SECONDS:
            return True
        else:
            return fail(f"durations differ by {abs(obj1.total_seconds() - obj2.total_seconds())} s")
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
            # point at the first differing character to make long-string diffs actionable
            idx = next((i for i, (c1, c2) in enumerate(zip(obj1, obj2)) if c1 != c2), min(len(obj1), len(obj2)))
            return fail(f"strings differ at index {idx} (lengths {len(obj1)} vs {len(obj2)}): ...{obj1[max(0, idx-20):idx+40]!r} vs ...{obj2[max(0, idx-20):idx+40]!r}")
    if not isinstance(obj1, Iterator) and type(obj1) != type(obj2):
        if obj1 is None or obj2 is None:
            return fail("the translated code produced None (no value) where the Java execution produced a value" if obj1 is None
                        else "the translated code produced a value where the Java execution produced null")
        return fail(f"types differ ({type(obj1).__name__} vs {type(obj2).__name__})")
    if isinstance(obj1, (BytesIO, StringIO)):
        if obj1.getvalue() == obj2.getvalue():
            return True
        return fail("stream contents differ", obj1.getvalue(), obj2.getvalue())
    if isinstance(obj1, dict):
        if obj1.keys() != obj2.keys():
            only1 = sorted(map(repr, set(obj1) - set(obj2)))[:5]; only2 = sorted(map(repr, set(obj2) - set(obj1)))[:5]
            return fail(f"dict keys differ (only on Python side: {only1}; only on Java side: {only2}; sizes {len(obj1)} vs {len(obj2)})", list(obj1.keys()), list(obj2.keys()))
        for key in obj1:
            r = recursive_equal(obj1[key], obj2[key], _child(_path, f"[{key!r}]"))
            if not r:
                return r
        return True
    elif isinstance(obj1, list):
        if len(obj1) != len(obj2):
            return fail(f"list lengths differ ({len(obj1)} vs {len(obj2)})")
        for i, (item1, item2) in enumerate(zip(obj1, obj2)):
            r = recursive_equal(item1, item2, _child(_path, f"[{i}]"))
            if not r:
                return r
        return True
    elif isinstance(obj1, set):
        if len(obj1) != len(obj2):
            return fail(f"set sizes differ ({len(obj1)} vs {len(obj2)})")
        for item1 in obj1:
            if not any(recursive_equal(item1, item2) for item2 in obj2):
                return fail(f"element {Mismatch._show(item1, 80)} has no equal element on the Java side")
        return True
    elif isinstance(obj1, urllib.parse.ParseResult):
        return recursive_equal(obj1._asdict(), obj2._asdict(), _path)
    elif isinstance(obj1, datetime):
        if obj1.timestamp() == obj2.timestamp():
            return True
        return fail(f"timestamps differ ({obj1.isoformat()} vs {obj2.isoformat()})")
    elif isinstance(obj1, tuple):
        if len(obj1) != len(obj2):
            return fail(f"tuple lengths differ ({len(obj1)} vs {len(obj2)})")
        for i, (item1, item2) in enumerate(zip(obj1, obj2)):
            r = recursive_equal(item1, item2, _child(_path, f"[{i}]"))
            if not r:
                return r
        return True
    elif isinstance(obj1, Iterator) and isinstance(obj2, Iterator):
        try:
            obj1_list = PeekableIterator(obj1).to_list()
            obj2_list = PeekableIterator(obj2).to_list()
            r = recursive_equal(obj1_list, obj2_list, _child(_path, "<iterator items>"))
            if r:
                return True
            if is_sublist(obj2_list, obj1_list):
                return True
            return fail("iterators yield different items", obj1_list, obj2_list)
        except ValueError as e:
            if "I/O operation on closed file" in str(e) or "I/O operation on uninitialized object" in str(e):
                return True
            else:
                raise
        except TypeError:
            return True
    elif isinstance(obj1, type({}.values())) and isinstance(obj2, type({}.values())):
        return recursive_equal(list(obj1), list(obj2), _path)
    elif hasattr(obj1, '__dict__') and hasattr(obj2, '__dict__'):
        obj1_dict_excluding_transient = {k: v for k, v in obj1.__dict__.items() if k in obj2.__dict__}
        missing = [k for k in obj2.__dict__ if k not in obj1.__dict__]
        if missing:
            return fail(f"{type(obj1).__name__} object lacks attributes present on the Java side: {missing[:8]}", sorted(obj1.__dict__), sorted(obj2.__dict__))
        for key in obj1_dict_excluding_transient:
            r = recursive_equal(obj1_dict_excluding_transient[key], obj2.__dict__[key], _child(_path, f".{key}"))
            if not r:
                return r
        return True
    if obj1 == obj2:
        return True
    return fail("values differ")


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
        for base in _adapter_bases(obj):   # library-superclass adapters (locks, timer tasks) need their own state
            try:
                base.__init__(obj)
            except Exception:
                pass
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
                    if "$" in field_name:
                        continue   # compiler-generated static (e.g. $SWITCH_TABLE$...): not part of the translated class
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
                    r = recursive_equal(ref_obj, field_value, f"static field {class_name}.{field_name}")
                    if not r:
                        return r
    return True
