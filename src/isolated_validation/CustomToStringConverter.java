package org.apache.commons.fileupload;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.FileDescriptor;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.FilterInputStream;
import java.io.FilterOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.CharBuffer;
import java.nio.charset.StandardCharsets;
import java.sql.Time;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.OutputStreamWriter;
import java.io.PipedInputStream;
import java.io.PipedOutputStream;
import java.io.PipedReader;
import java.io.PipedWriter;
import java.io.PrintStream;
import java.io.PrintWriter;
import java.io.Reader;
import java.io.StringReader;
import java.io.StringWriter;
import java.io.Writer;
import java.util.AbstractMap;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.BitSet;
import java.util.Calendar;
import java.util.Collection;
import java.util.Collections;
import java.util.Date;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.Map;
import java.util.Properties;
import java.util.Scanner;
import java.util.Set;
import java.util.Spliterator;
import java.util.Spliterators;
import java.util.Iterator;
import java.util.List;
import java.util.TimeZone;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import java.util.zip.CRC32;

import org.json.JSONArray;
import org.json.JSONObject;

public class CustomToStringConverter {

    public static int nestedIteratorHashCode = -1;

    public static JSONObject customToJSONObject(Object obj) {
        return customToJSONObject(obj, new HashSet<>());
    }

    private static JSONObject customToJSONObject(Object obj, Set<Integer> seen) {
        int objId = System.identityHashCode(obj);

        if (seen.contains(objId) && !(obj instanceof Enum<?>)) {
            JSONObject ref = new JSONObject();
            Class<?> seenObjClazz = obj.getClass();
            if (seenObjClazz.getName().contains("java.")) {
                ref.put("type", seenObjClazz.getName());
            } else {
                if (isTestClass(seenObjClazz)) {
                    ref.put("type", "src.test." + seenObjClazz.getName());
                } else {
                    ref.put("type", "src.main." + seenObjClazz.getName());
                }
            }
            ref.put("memory_address", objId);
            ref.put("note", "circular_reference");
            return ref;
        }

        seen.add(objId);

        if ((obj instanceof Enum<?>) && !(obj instanceof TimeUnit) && !(obj instanceof ChronoUnit)) {
            JSONObject enumDetails = new JSONObject();
            Class<?> clazz = obj.getClass();
            Enum<?> enumObj = (Enum<?>) obj;
            if (isTestClass(clazz)) {
                enumDetails.put("type", "src.test." + clazz.getName());
            } else {
                enumDetails.put("type", "src.main." + clazz.getName());
            }
            enumDetails.put("enum_name", (enumObj.name()));

            boolean foundConcreteValue = false;
            // Try to find the field representing the associated value
            try {
                Field[] fields = clazz.getDeclaredFields();
                for (Field field : fields) {
                    if (Modifier.isPrivate(field.getModifiers())
                            && !Modifier.isStatic(field.getModifiers())
                            && !Modifier.isTransient(field.getModifiers())) {
                        field.setAccessible(true);
                        Object value = field.get(enumObj);
                        enumDetails.put("enum_value", value != null ? new JSONObject(customToString(value, seen)) : JSONObject.NULL);
                        foundConcreteValue = true;
                        break;
                    }
                }
            } catch (Exception e) {
                enumDetails.put("enum_value", JSONObject.NULL);
            }
            if (!foundConcreteValue) {
                enumDetails.put("enum_value", new JSONObject(customToString(enumObj.ordinal(), seen)));
            }
            return enumDetails;
        }

        if (obj == null) {
            JSONObject nullObject = new JSONObject();
            nullObject.put("type", "null");
            return nullObject;
        }
        String fullPackage = CustomToStringConverter.class.getPackage().getName();
        String[] basePackageParts = fullPackage.split("\\.");
        String basePackage = "";
        if (basePackageParts.length > 2) {
            basePackage = basePackageParts[0] + "." + basePackageParts[1] + "." + basePackageParts[2];
        } else if (basePackageParts.length > 1) {
            basePackage = basePackageParts[0] + "." + basePackageParts[1];
        } else {
            basePackage = basePackageParts[0];
        }
        Package objPackage = obj.getClass().getPackage();
        if (objPackage == null && !(obj.getClass().isArray())) {
            JSONObject objDetails = new JSONObject();
            objDetails.put("type", getTypeName(obj, basePackage));
            objDetails.put("value", obj != null ? obj.toString() : JSONObject.NULL);
            return objDetails;
        }
        JSONObject bufferedReaderChildDetails = null;
        JSONObject filterInputStreamChildDetails = null;
        JSONObject filterOutputStreamChildDetails = null;
        boolean handlingNestedIterator = false;
        if (objPackage != null && objPackage.getName().startsWith(basePackage) && (obj instanceof BufferedReader)) {
            // Edge case: child classes of BufferedReader...
            bufferedReaderChildDetails = new JSONObject();
            bufferedReaderChildDetails = handleBufferedReader((BufferedReader) obj, basePackage, seen);
        } else if (objPackage != null && objPackage.getName().startsWith(basePackage) && (obj instanceof FilterInputStream)) {
            // Edge case: child classes of FilterInputStream...
            filterInputStreamChildDetails = new JSONObject();
            filterInputStreamChildDetails = handleFilterInputStream((FilterInputStream) obj, basePackage, seen);
        } else if (objPackage != null && objPackage.getName().startsWith(basePackage) && (obj instanceof FilterOutputStream)) {
            // Edge case: child classes of FilterOutputStream...
            filterOutputStreamChildDetails = new JSONObject();
            filterOutputStreamChildDetails = handleFilterOutputStream((FilterOutputStream) obj, basePackage, seen);
        } else if (objPackage != null && objPackage.getName().startsWith(basePackage) && (obj instanceof Iterator) && (obj.getClass().getEnclosingClass() != null)) {
            // Edge case: nested iterator
            handlingNestedIterator = true;
            nestedIteratorHashCode = System.identityHashCode(obj);
        }
        if (obj.getClass().isArray() || (basePackage != null && !objPackage.getName().startsWith(basePackage))) {
            JSONObject objDetails = new JSONObject();
            JSONObject extendedDetails = obj.getClass().isArray() ? null : handleExtendedLibraryObject(obj, basePackage, seen);
            if (extendedDetails != null) {
                objDetails = extendedDetails;
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof Iterator) {
                objDetails = handleIterator((Iterator<?>) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof BitSet) {
                objDetails = handleBitSet((BitSet) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof Method) {
                objDetails = handleMethod((Method) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof Constructor) {
                objDetails = handleConstructor((Constructor<?>) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof Properties) {
                objDetails = handleProperties((Properties) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof Map) {
                objDetails = handleMap((Map<?, ?>) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof Collection) {
                objDetails = handleCollection((Collection<?>) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof Throwable) {
                objDetails = handleThrowable((Throwable) obj, basePackage, seen);
            } else if (obj instanceof StringReader) {
                objDetails = handleStringReader((StringReader) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof StringWriter) {
                objDetails = handleStringWriter((StringWriter) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof BufferedReader) {
                objDetails = handleBufferedReader((BufferedReader) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof ByteArrayInputStream) {
                objDetails = handleByteArrayInputStream((ByteArrayInputStream) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof ByteArrayOutputStream) {
                objDetails = handleByteArrayOutputStream((ByteArrayOutputStream) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof FileInputStream) {
                objDetails = handleFileInputStream((FileInputStream) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof FileOutputStream) {
                objDetails = handleFileOutputStream((FileOutputStream) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof PrintWriter) {
                objDetails = handlePrintWriter((PrintWriter) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof Date || obj instanceof Calendar || obj instanceof Clock || obj instanceof Instant
                || obj instanceof TimeUnit || obj instanceof ChronoUnit || obj instanceof Duration
                || obj instanceof TimeZone || obj instanceof sun.util.calendar.ZoneInfo) {
                objDetails = handleDateTime(obj);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof Class) {
                Class<?> clazz = (Class<?>) obj;
                objDetails.put("type", getTypeName(clazz, basePackage));
                objDetails.put("value", clazz.getName());
            } else if (obj instanceof Stream) {
                objDetails = handleStream((Stream<?>) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof InputStreamReader) {
                objDetails = handleInputStreamReader((InputStreamReader) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof OutputStreamWriter) {
                objDetails = handleOutputStreamWriter((OutputStreamWriter) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof PipedReader) {
                objDetails = handlePipedReader((PipedReader) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof PipedWriter) {
                objDetails = handlePipedWriter((PipedWriter) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof FilterInputStream) {
                objDetails = handleFilterInputStream((FilterInputStream) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof FilterOutputStream) {
                objDetails = handleFilterOutputStream((FilterOutputStream) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof PipedInputStream) {
                objDetails = handlePipedInputStream((PipedInputStream) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof PipedOutputStream) {
                objDetails = handlePipedOutputStream((PipedOutputStream) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof PrintStream) {
                objDetails = handlePrintStream((PrintStream) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof Matcher) {
                objDetails = handleMatcher((Matcher) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof CRC32) {
                objDetails = handleCRC32((CRC32) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj instanceof CharBuffer) {
                objDetails = handleCharBuffer((CharBuffer) obj, basePackage, seen);
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else if (obj.getClass().isArray()) {
                if (obj.getClass().getComponentType().isPrimitive()) {
                    objDetails = handlePrimitiveArray(obj, basePackage, seen);
                } else {
                    objDetails = handleCollection(Arrays.asList((Object[]) obj), basePackage, seen);
                }
                objDetails.put("memory_address", System.identityHashCode(obj));
            } else {
                objDetails.put("type", getTypeName(obj, basePackage));
                objDetails.put("value", obj != null ? obj.toString() : JSONObject.NULL);
                objDetails.put("memory_address", System.identityHashCode(obj));
            }
            return objDetails;
        }
        
        JSONObject jsonObject = new JSONObject();
        if (bufferedReaderChildDetails != null) {
            jsonObject = bufferedReaderChildDetails;
        } else if (filterInputStreamChildDetails != null) {
            jsonObject = filterInputStreamChildDetails;
        } else if (filterOutputStreamChildDetails != null) {
            jsonObject = filterOutputStreamChildDetails;
        }
        jsonObject.put("type", getTypeName(obj, basePackage));
    
        JSONObject staticFieldsJson = new JSONObject();
        JSONObject instanceFieldsJson = new JSONObject();
    
        Class<?> originalClass = obj.getClass();
        Class<?> currentClass = obj.getClass();
        Set<String> processedFields = new HashSet<>();
    
        while (currentClass != null) {
            if (handlingNestedIterator) {
                try {
                    Field nestedIteratorOuterClassInstanceRef = currentClass.getDeclaredField("this$0");
                    nestedIteratorOuterClassInstanceRef.setAccessible(true);
                    Object nestedIteratorOuterClassInstanceValue = nestedIteratorOuterClassInstanceRef.get(obj);
                    JSONObject nestedIteratorOuterClassInstanceFieldDetails = new JSONObject();
                    nestedIteratorOuterClassInstanceFieldDetails.put("modifier", "private");
                    if (isTestClass(nestedIteratorOuterClassInstanceRef.getType())) {
                        nestedIteratorOuterClassInstanceFieldDetails.put("type", "src.test." + nestedIteratorOuterClassInstanceRef.getType().getName());
                    } else {
                        nestedIteratorOuterClassInstanceFieldDetails.put("type", "src.main." + nestedIteratorOuterClassInstanceRef.getType().getName());
                    }
                    if (nestedIteratorOuterClassInstanceValue != null) {
                        nestedIteratorOuterClassInstanceFieldDetails.put("value", new JSONObject(customToString(nestedIteratorOuterClassInstanceValue, seen)));
                    } else {
                        nestedIteratorOuterClassInstanceFieldDetails.put("value", JSONObject.NULL);
                    }
                    instanceFieldsJson.put(nestedIteratorOuterClassInstanceRef.getType().getSimpleName(), nestedIteratorOuterClassInstanceFieldDetails);
                } catch(Exception e) {
                    e.printStackTrace();
                }
                handlingNestedIterator = false;
            }
            Field[] fields = currentClass.getDeclaredFields();
            for (Field field : fields) {
                if (field.isSynthetic() || field.getName().equals("watchdog")) {
                    continue;
                }
                field.setAccessible(true);
                try {
                    JSONObject fieldDetails = new JSONObject();
    
                    String modifier = Modifier.toString(field.getModifiers());

                    Object fieldValue = Modifier.isStatic(field.getModifiers()) ? field.get(null) : field.get(obj);;

                    // Include fields based on their access level
                    if (modifier.contains("public")) {
                        fieldDetails.put("modifier", "public");
                    } else if (modifier.contains("protected")) {
                        fieldDetails.put("modifier", "protected");
                    } else if (modifier.contains("private")) {
                        fieldDetails.put("modifier", "private");
                        if (!originalClass.equals(currentClass)) {
                            if (currentClass.getName().contains("java.")) {
                                fieldDetails.put("declaring_class", currentClass.getName());
                            } else {
                                if (isTestClass(currentClass)) {
                                    fieldDetails.put("declaring_class", "src.test." + currentClass.getName());
                                } else {
                                    fieldDetails.put("declaring_class", "src.main." + currentClass.getName());
                                }
                            }
                            if (processedFields.contains(field.getName())) {
                                fieldDetails.put("shadowed", "true");
                            }
                        }
                    } else {
                        fieldDetails.put("modifier", "public");
                    }
    
                    if (System.identityHashCode(fieldValue) == nestedIteratorHashCode) {
                        nestedIteratorHashCode = -1;
                        continue;
                    }
                    Package fieldPackage = field.getType().getPackage();
                    String[] fieldPackageParts = new String[0];
                    if (fieldPackage != null) {
                        fieldPackageParts = fieldPackage.getName().split("\\.");
                    }
                    String fieldPackageName = "";
                    if (fieldPackageParts.length > 2) {
                        fieldPackageName = fieldPackageParts[0] + "." + fieldPackageParts[1] + "." + fieldPackageParts[2];
                    }
    
                    if (fieldPackage != null && fieldPackageName.startsWith(basePackage)) {
                        // Handle repository-level type
                        if (isTestClass(field.getType())) {
                            fieldDetails.put("type", "src.test." + field.getType().getName());
                        } else {
                            fieldDetails.put("type", "src.main." + field.getType().getName());
                        }
                        if (fieldValue != null) {
                            if (fieldValue.getClass().equals(obj.getClass())) {
                                fieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                                fieldDetails.put("note", "instance of self-referential field");
                            } else {
                                fieldDetails.put("value", new JSONObject(customToString(fieldValue, seen)));
                                fieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                            }
                        } else {
                            fieldDetails.put("value", JSONObject.NULL);
                        }
                    } else {
                        JSONObject specialFieldDetails = new JSONObject();
                        JSONObject extendedFieldDetails = (fieldValue == null || fieldValue.getClass().isArray()) ? null : handleExtendedLibraryObject(fieldValue, basePackage, seen);
                        if (fieldValue == null) {
                            fieldDetails.put("type", "null");
                            fieldDetails.put("value", "null");
                        } else if (extendedFieldDetails != null) {
                            specialFieldDetails = extendedFieldDetails;
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof BitSet) {
                            specialFieldDetails = handleBitSet((BitSet) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof Method) {
                            specialFieldDetails = handleMethod((Method) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof Constructor) {
                            specialFieldDetails = handleConstructor((Constructor<?>) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof Iterator) {
                            specialFieldDetails = handleIterator((Iterator<?>) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof Properties) {
                            specialFieldDetails = handleProperties((Properties) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof Map) {
                            specialFieldDetails = handleMap((Map<?, ?>) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof Collection) {
                            specialFieldDetails = handleCollection((Collection<?>) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof StringReader) {
                            specialFieldDetails = handleStringReader((StringReader) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof StringWriter) {
                            specialFieldDetails = handleStringWriter((StringWriter) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof Throwable) {
                            specialFieldDetails = handleThrowable((Throwable) fieldValue, basePackage, seen);
                        } else if (fieldValue instanceof BufferedReader) {
                            specialFieldDetails = handleBufferedReader((BufferedReader) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof ByteArrayInputStream) {
                            specialFieldDetails = handleByteArrayInputStream((ByteArrayInputStream) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof ByteArrayOutputStream) {
                            specialFieldDetails = handleByteArrayOutputStream((ByteArrayOutputStream) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof FileInputStream) {
                            specialFieldDetails = handleFileInputStream((FileInputStream) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof FileOutputStream) {
                            specialFieldDetails = handleFileOutputStream((FileOutputStream) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof PrintWriter) {
                            specialFieldDetails = handlePrintWriter((PrintWriter) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof Date || fieldValue instanceof Calendar || fieldValue instanceof Clock || fieldValue instanceof Instant
                            || fieldValue instanceof TimeUnit || fieldValue instanceof ChronoUnit || fieldValue instanceof Duration
                            || fieldValue instanceof TimeZone || fieldValue instanceof sun.util.calendar.ZoneInfo) {
                            specialFieldDetails = handleDateTime(fieldValue);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue.getClass().isArray()) {
                            if (fieldValue.getClass().getComponentType().isPrimitive()) {
                                specialFieldDetails = handlePrimitiveArray(fieldValue, basePackage, seen);
                            } else {
                                specialFieldDetails = handleCollection(Arrays.asList((Object[]) fieldValue), basePackage, seen);
                            }
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof Class) {
                            Class<?> clazz = (Class<?>) fieldValue;
                            fieldDetails.put("type", getTypeName(clazz, basePackage));
                            fieldDetails.put("value", clazz.getName());
                        } else if (fieldValue instanceof Stream) {
                            specialFieldDetails = handleStream((Stream<?>) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof InputStreamReader) {
                            specialFieldDetails = handleInputStreamReader((InputStreamReader) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof OutputStreamWriter) {
                            specialFieldDetails = handleOutputStreamWriter((OutputStreamWriter) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof PipedReader) {
                            specialFieldDetails = handlePipedReader((PipedReader) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof PipedWriter) {
                            specialFieldDetails = handlePipedWriter((PipedWriter) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof FilterInputStream) {
                            specialFieldDetails = handleFilterInputStream((FilterInputStream) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof FilterOutputStream) {
                            specialFieldDetails = handleFilterOutputStream((FilterOutputStream) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof PipedInputStream) {
                            specialFieldDetails = handlePipedInputStream((PipedInputStream) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof PipedOutputStream) {
                            specialFieldDetails = handlePipedOutputStream((PipedOutputStream) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof PrintStream) {
                            specialFieldDetails = handlePrintStream((PrintStream) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof Matcher) {
                            specialFieldDetails = handleMatcher((Matcher) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof CRC32) {
                            specialFieldDetails = handleCRC32((CRC32) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else if (fieldValue instanceof CharBuffer) {
                            specialFieldDetails = handleCharBuffer((CharBuffer) fieldValue, basePackage, seen);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        } else {
                            fieldDetails.put("type", field.getType().getTypeName());
                            fieldDetails.put("value", fieldValue != null ? fieldValue.toString() : JSONObject.NULL);
                            specialFieldDetails.put("memory_address", System.identityHashCode(fieldValue));
                        }
                        for (String extraDetailsKey : specialFieldDetails.keySet()) {
                            fieldDetails.put(extraDetailsKey, specialFieldDetails.get(extraDetailsKey));
                        }
                    }
    
                    if (Modifier.isStatic(field.getModifiers())) {
                        if (!staticFieldsJson.has(field.getName())) {
                            staticFieldsJson.put(field.getName(), fieldDetails);
                        } else {
                            staticFieldsJson.put(field.getName() + "_HIDDEN_FIELD___", fieldDetails);
                        }
                    } else {
                        if (!instanceFieldsJson.has(field.getName())) {
                            instanceFieldsJson.put(field.getName(), fieldDetails);
                        } else {
                            instanceFieldsJson.put(field.getName() + "_HIDDEN_FIELD___", fieldDetails);
                        }
                    }
    
                    processedFields.add(field.getName());
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }
            if (bufferedReaderChildDetails != null || filterInputStreamChildDetails != null || filterOutputStreamChildDetails != null) {
                break;
            }
            currentClass = currentClass.getSuperclass();
        }
    
        jsonObject.put("static_fields", staticFieldsJson);
        jsonObject.put("instance_fields", instanceFieldsJson);
        jsonObject.put("memory_address", System.identityHashCode(obj));
    
        return jsonObject;
    }

    private static JSONObject handleIterator(Iterator<?> fieldValue, String basePackage, Set<Integer> seen) {
        JSONObject iteratorDetails = new JSONObject();
        Object underlyingCollection = getUnderlyingCollection(fieldValue);
        JSONObject underlyingCollectionDetails = null;
        iteratorDetails.put("type", Iterator.class.getName());
        if (underlyingCollection instanceof Map) {
            underlyingCollectionDetails = handleMap((Map<?, ?>) underlyingCollection, basePackage, seen);
            iteratorDetails.put("collection_details", underlyingCollectionDetails);
        } else if (underlyingCollection instanceof Collection) {
            underlyingCollectionDetails = handleCollection((Collection<?>) underlyingCollection, basePackage, seen);
            iteratorDetails.put("collection_details", underlyingCollectionDetails);
        }
        return iteratorDetails;
    }
    
    public static JSONObject handleProperties(Object fieldValue, String basePackage, Set<Integer> seen) {
        Properties properties = (Properties) fieldValue;
        JSONObject mapDetails = new JSONObject();
        JSONArray keysArray = new JSONArray();
        JSONArray valuesArray = new JSONArray();

        for (Enumeration<?> e = properties.propertyNames(); e.hasMoreElements(); ) {
            Object key = e.nextElement();
            Object value = properties.getProperty((String) key);

            keysArray.put(key != null ? new JSONObject(customToString(key, seen)) : JSONObject.NULL);
            valuesArray.put(value != null ? new JSONObject(customToString(value, seen)) : JSONObject.NULL);
        }

        mapDetails.put("type", getTypeName(fieldValue, basePackage));
        mapDetails.put("keys", keysArray);
        mapDetails.put("values", valuesArray);
        return mapDetails;
    }
    
    public static JSONObject handleMap(Object fieldValue, String basePackage, Set<Integer> seen) {
        JSONObject mapDetails = new JSONObject();
        Map<?, ?> map = (Map<?, ?>) fieldValue;
        JSONArray keysArray = new JSONArray();
        JSONArray valuesArray = new JSONArray();
    
        for (Map.Entry<?, ?> entry : map.entrySet()) {
            Object key = entry.getKey();
            JSONObject keyObject = new JSONObject();
            if (key != null) {
                keyObject = new JSONObject(customToString(key, seen));
            } else {
                keyObject.put("value", JSONObject.NULL);
            }
            keysArray.put(keyObject);
    
            Object value = entry.getValue();
            JSONObject valueObject = new JSONObject();
            if (value != null) {
                valueObject = new JSONObject(customToString(value, seen));
            } else {
                valueObject.put("value", JSONObject.NULL);
            }
            valuesArray.put(valueObject);
        }
    
        mapDetails.put("type", getTypeName(fieldValue, basePackage));
        mapDetails.put("keys", keysArray);
        mapDetails.put("values", valuesArray);
        return mapDetails;
    }

    private static JSONObject handleStringReader(StringReader reader, String basePackage, Set<Integer> seen) {
        JSONObject srDetails = new JSONObject();
        srDetails.put("type", getTypeName(reader, basePackage));
        Class<?> readerClass = reader.getClass();
    
        try {
            Field strField = readerClass.getDeclaredField("str");
            strField.setAccessible(true);
            String backingString = (String) strField.get(reader);
            srDetails.put("value", backingString);
    
            Field posField = readerClass.getDeclaredField("next");
            posField.setAccessible(true);
            int position = posField.getInt(reader);
            srDetails.put("position", position);
        } catch (Exception e) {
            e.printStackTrace();
        }
    
        return srDetails;
    }

    private static JSONObject handleStringWriter(StringWriter writer, String basePackage, Set<Integer> seen) {
        JSONObject swDetails = new JSONObject();
        swDetails.put("type", getTypeName(writer, basePackage));
        Class<?> writerClass = writer.getClass();
    
        try {
            Field bufferField = writerClass.getDeclaredField("buf");
            bufferField.setAccessible(true);
            StringBuffer buf = (StringBuffer) bufferField.get(writer);
            String currentContent = buf.toString();
            swDetails.put("value", currentContent);
            swDetails.put("position", buf.length()); 
        } catch (Exception e) {
            e.printStackTrace();
        }
    
        return swDetails;
    }

    private static JSONObject handleCRC32(CRC32 crc, String basePackage, Set<Integer> seen) {
        JSONObject crcDetails = new JSONObject();
        crcDetails.put("type", getTypeName(crc, basePackage));
        try {
            long value = crc.getValue();
            crcDetails.put("value", Long.toString(value));
        } catch (Exception e) {
            e.printStackTrace();
        }
        return crcDetails;
    }
    
    private static JSONObject handleStream(Object fieldValue, String basePackage, Set<Integer> seen) {
        JSONObject streamDetails = new JSONObject();
        Stream<?> stream = (Stream<?>) fieldValue;
        try {
            Field sourceField = stream.getClass().getDeclaredField("source");
            sourceField.setAccessible(true);
            Object source = sourceField.get(stream);
            if (source instanceof Iterator) {
                return handleIterator((Iterator<?>)source, basePackage, seen);
            } else if (source instanceof Collection) {
                return handleCollection((Collection<?>)source, basePackage, seen);
            } else if (source instanceof Spliterator) {
                try {
                    Field itField = source.getClass().getDeclaredField("it");
                    itField.setAccessible(true);
                    Object originalIterator = itField.get(source);
                    return handleIterator((Iterator<?>)originalIterator, basePackage, seen);
                } catch (Throwable t) {
                    Field outer = source.getClass().getDeclaredField("this$0");
                    outer.setAccessible(true);
                    Object collection = outer.get(source);
                    if (collection instanceof Collection<?>) {
                        Iterator<?> it = ((Collection<?>) collection).iterator();
                        return handleIterator(it, basePackage, seen);
                    } else {
                        streamDetails.put("type", getTypeName(fieldValue, basePackage));
                        streamDetails.put("value", JSONObject.NULL);
                        return streamDetails;
                    }
                }
            }
        } catch (Throwable t) {
            try {
                Class<?> abstractPipeline = Class.forName("java.util.stream.AbstractPipeline");
                Field spliteratorField = abstractPipeline.getDeclaredField("sourceSpliterator");
                spliteratorField.setAccessible(true);
                Object spliterator = spliteratorField.get(stream);
                if (spliterator instanceof Spliterator) {
                    return handleIterator(Spliterators.iterator((Spliterator<?>) spliterator), basePackage, seen);
                }
            } catch (Throwable t2) {
                t.printStackTrace();
                streamDetails.put("type", getTypeName(fieldValue, basePackage));
                streamDetails.put("value", JSONObject.NULL);
                return streamDetails;
            }
        }
        streamDetails.put("type", getTypeName(fieldValue, basePackage));
        streamDetails.put("value", JSONObject.NULL);
        return streamDetails;
    }

    public static JSONObject handleCollection(Object fieldValue, String basePackage, Set<Integer> seen) {
        JSONObject collectionDetails = new JSONObject();
        Collection<?> collection = (Collection<?>) fieldValue;
        JSONArray jsonArray = new JSONArray();
    
        for (Object element : collection) {
            jsonArray.put(new JSONObject(customToString(element, seen)));
        }
    
        collectionDetails.put("type", getTypeName(fieldValue, basePackage));
        collectionDetails.put("collection_elements", jsonArray);
        return collectionDetails;
    }

    private static JSONObject handleCharBuffer(CharBuffer charBuffer, String basePackage, Set<Integer> seen) {
        JSONObject bufferDetails = new JSONObject();
        JSONArray jsonArray = new JSONArray();
    
        CharBuffer duplicate = charBuffer.duplicate();
    
        while (duplicate.hasRemaining()) {
            char c = duplicate.get();
            jsonArray.put(new JSONObject(customToString(c, seen)));
        }
    
        bufferDetails.put("type", getTypeName(charBuffer, basePackage));
        bufferDetails.put("buffer_elements", jsonArray);
        bufferDetails.put("remaining", charBuffer.remaining()); // optional: keep metadata
        bufferDetails.put("capacity", charBuffer.capacity());   // optional
        bufferDetails.put("position", charBuffer.position());   // optional
        bufferDetails.put("limit", charBuffer.limit());         // optional
    
        return bufferDetails;
    }
    

    private static JSONObject handlePrimitiveArray(Object array, String basePackage, Set<Integer> seen) {
        JSONObject arrayDetails = new JSONObject();
        JSONArray jsonArray = new JSONArray();
    
        int length = java.lang.reflect.Array.getLength(array);
        for (int i = 0; i < length; i++) {
            Object element = java.lang.reflect.Array.get(array, i);
            JSONObject elementObject = new JSONObject();
            elementObject.put("type", getTypeName(element, basePackage));
            elementObject.put("value", element != null ? element.toString() : JSONObject.NULL);
            jsonArray.put(elementObject);
        }
    
        arrayDetails.put("type", getTypeName(array, basePackage));
        arrayDetails.put("collection_elements", jsonArray);
        return arrayDetails;
    }


    private static JSONObject handleThrowable(Throwable throwable, String basePackage, Set<Integer> seen) {
        JSONObject throwableDetails = new JSONObject();

        throwableDetails.put("type", "java.lang.Throwable");
        throwableDetails.put("throwable_type", throwable.getClass().getName());
    
        if (throwable.getMessage() != null) {
            throwableDetails.put("message", throwable.getMessage());
        } else {
            throwableDetails.put("message", JSONObject.NULL);
        }
    
        return throwableDetails;
    }

    private static JSONObject handleConstructor(Constructor<?> ctor, String basePackage, Set<Integer> seen) {
        JSONObject ctorDetails = new JSONObject();
        ctorDetails.put("type", "java.lang.reflect.Constructor");
        if (!isTestClass(ctor.getDeclaringClass())) {
            ctorDetails.put("ctor_declaring_class", "src.main." + ctor.getDeclaringClass().getName());
        } else {
            ctorDetails.put("ctor_declaring_class", "src.test." + ctor.getDeclaringClass().getName());
        }
        return ctorDetails;
    }

    private static JSONObject handleMethod(Method method, String basePackage, Set<Integer> seen) {
        JSONObject methodDetails = new JSONObject();
        methodDetails.put("type", "java.lang.reflect.Method");
        if (!isTestClass(method.getDeclaringClass())) {
            methodDetails.put("method_declaring_class", "src.main." + method.getDeclaringClass().getName());
        } else {
            methodDetails.put("method_declaring_class", "src.test." + method.getDeclaringClass().getName());
        }
        int modifiers = method.getModifiers();
        if (Modifier.isProtected(modifiers)) {
            methodDetails.put("modifier", "protected");
        } else if (Modifier.isPrivate(modifiers)) {
            methodDetails.put("modifier", "private");
        } else {
            methodDetails.put("modifier", "public");
        }
        methodDetails.put("name", method.getName());
        return methodDetails;
    }

    private static JSONObject handleBufferedReader(BufferedReader reader, String basePackage, Set<Integer> seen) {
        JSONObject readerDetails = new JSONObject();
        readerDetails.put("type", reader.getClass().getName());

        try {
            Field inField = BufferedReader.class.getDeclaredField("in");
            inField.setAccessible(true);
            Object innerReader = inField.get(reader);

            if (innerReader instanceof InputStreamReader) {
                InputStreamReader inputStreamReader = (InputStreamReader) innerReader;

                Field lockField = Reader.class.getDeclaredField("lock");
                lockField.setAccessible(true);
                Object lockObject = lockField.get(inputStreamReader);

                if (lockObject == System.in) {
                    readerDetails.put("special_note", "System.in");
                } else if (lockObject instanceof ByteArrayInputStream) {
                    readerDetails.put("special_note", "byte_stream");
                    readerDetails.put("byte_stream", handleByteArrayInputStream((ByteArrayInputStream) lockObject, basePackage, seen));
                } else {
                    readerDetails.put("special_note", "unknown stream lock: " + lockObject.getClass().getName());
                }

            } else if (innerReader instanceof StringReader) {
                Field strField = StringReader.class.getDeclaredField("str");
                Field nextField = StringReader.class.getDeclaredField("next");
                strField.setAccessible(true);
                nextField.setAccessible(true);

                String content = (String) strField.get(innerReader);
                int position = (int) nextField.get(innerReader);

                readerDetails.put("content", content);
                readerDetails.put("position", position);

            } else if (innerReader instanceof PipedReader) {
                readerDetails.put("special_note", "byte_stream");
                readerDetails.put("byte_stream", handlePipedReader((PipedReader) innerReader, basePackage, seen));
            } else {
                readerDetails.put("special_note", "Unsupported inner reader: " + innerReader.getClass().getName());
            }

        } catch (Exception e) {
            // innerReader is null (already closed)
            readerDetails.put("content", "");
        }

        return readerDetails;
    }

    private static JSONObject handlePipedReader(PipedReader reader, String basePackage, Set<Integer> seen) {
        JSONObject readerDetails = new JSONObject();
        readerDetails.put("type", getTypeName(reader, basePackage));
    
        try {
            Field bufferField = PipedReader.class.getDeclaredField("buffer");
            Field inField = PipedReader.class.getDeclaredField("in");
    
            bufferField.setAccessible(true);
            inField.setAccessible(true);
    
            char[] charBuffer = (char[]) bufferField.get(reader);
            int position = inField.getInt(reader);
    
            if (position > 0) {
                String content = new String(charBuffer, 0, position);
                byte[] byteArray = content.getBytes(StandardCharsets.UTF_8);
    
                readerDetails.put("byte_array", handlePrimitiveArray(byteArray, basePackage, seen));
                readerDetails.put("position", position);
            } else {
                readerDetails.put("byte_array", handlePrimitiveArray(new byte[0], basePackage, seen));
                readerDetails.put("position", 0);
            }
    
        } catch (Exception e) {
            e.printStackTrace();
        }
    
        return readerDetails;
    }

    private static JSONObject handlePipedWriter(PipedWriter writer, String basePackage, Set<Integer> seen) {
        JSONObject writerDetails = new JSONObject();
        writerDetails.put("type", getTypeName(writer, basePackage));

        try {
            Field sinkField = PipedWriter.class.getDeclaredField("sink");
            sinkField.setAccessible(true);
            Object pipedReader = sinkField.get(writer);

            if (pipedReader instanceof PipedReader) {
                JSONObject innerReaderDetails = handlePipedReader((PipedReader) pipedReader, basePackage, seen);
                writerDetails.put("byte_array", innerReaderDetails.get("byte_array"));
                writerDetails.put("size", innerReaderDetails.get("position"));
            }

        } catch (Exception e) {
            e.printStackTrace();
        }

        return writerDetails;
    }

    private static JSONObject handleFilterInputStream(FilterInputStream fis, String basePackage, Set<Integer> seen) {
        JSONObject details = new JSONObject();
        details.put("type", fis.getClass().getName());

        try {
            Field inField = FilterInputStream.class.getDeclaredField("in");
            inField.setAccessible(true);
            InputStream inner = (InputStream) inField.get(fis);

            if (inner instanceof ByteArrayInputStream) {
                details.put("stream_type", "byte_stream");
                details.put("stream_details", handleByteArrayInputStream((ByteArrayInputStream) inner, basePackage, seen));
            } else if (inner instanceof PipedInputStream) {
                details.put("stream_type", "byte_stream");
                details.put("stream_details", handlePipedInputStream((PipedInputStream) inner, basePackage, seen));
            } else if (inner instanceof FileInputStream) {
                details.put("stream_type", "file_stream");
                details.put("stream_details", handleFileInputStream((FileInputStream) inner, basePackage, seen));
            } else if (inner != null) {
                JSONObject innerDetails = handleAnyInputStream(inner, basePackage, seen, 1);
                details.put("stream_type", innerDetails.has("file_path") ? "file_stream" : (innerDetails.has("stream_type") && innerDetails.optString("stream_type").equals("unknown") ? "unknown" : "byte_stream"));
                details.put("stream_details", innerDetails);
                details.put("stream_class", inner.getClass().getName());
            } else {
                details.put("stream_type", "unknown");
                details.put("stream_class", "null");
            }
        } catch (Exception e) {
            details.put("error", e.toString());
        }

        return details;
    }

    private static JSONObject handleFilterOutputStream(FilterOutputStream fos, String basePackage, Set<Integer> seen) {
        JSONObject details = new JSONObject();
        details.put("type", fos.getClass().getName());

        try {
            Field outField = FilterOutputStream.class.getDeclaredField("out");
            outField.setAccessible(true);
            OutputStream inner = (OutputStream) outField.get(fos);

            if (inner instanceof ByteArrayOutputStream) {
                details.put("stream_type", "byte_stream");
                details.put("stream_details", handleByteArrayOutputStream((ByteArrayOutputStream) inner, basePackage, seen));
            } else if (inner instanceof PipedOutputStream) {
                details.put("stream_type", "byte_stream");
                details.put("stream_details", handlePipedOutputStream((PipedOutputStream) inner, basePackage, seen));
            } else if (inner instanceof PrintStream) {
                details.put("stream_type", "byte_stream");
                details.put("stream_details", handlePrintStream((PrintStream) inner, basePackage, seen));
            } else if (inner instanceof FileOutputStream) {
                details.put("stream_type", "file_stream");
                details.put("stream_details", handleFileOutputStream((FileOutputStream) inner, basePackage, seen));
            } else if (inner != null) {
                JSONObject innerDetails = handleAnyOutputStream(inner, basePackage, seen, 1);
                details.put("stream_type", innerDetails.has("file_path") ? "file_stream" : (innerDetails.has("stream_type") && innerDetails.optString("stream_type").equals("unknown") ? "unknown" : "byte_stream"));
                details.put("stream_details", innerDetails);
                details.put("stream_class", inner.getClass().getName());
            } else {
                details.put("stream_type", "unknown");
                details.put("stream_class", "null");
            }
        } catch (Exception e) {
            details.put("error", e.toString());
        }

        return details;
    }

    private static JSONObject handlePrintStream(PrintStream ps, String basePackage, Set<Integer> seen) {
        JSONObject psDetails = new JSONObject();
        psDetails.put("type", ps.getClass().getName());
    
        try {
            Field outField = FilterOutputStream.class.getDeclaredField("out");
            outField.setAccessible(true);
            OutputStream os = (OutputStream) outField.get(ps);
    
            if (os instanceof ByteArrayOutputStream) {
                psDetails.put("special_note", "byte_stream");
    
                ByteArrayOutputStream baos = (ByteArrayOutputStream) os;
                byte[] byteArray = baos.toByteArray();
                psDetails.put("byte_array", handlePrimitiveArray(byteArray, basePackage, seen));
    
            } else if (os instanceof PipedOutputStream) {
                psDetails.put("special_note", "byte_stream");
    
                JSONObject fileDetails = handlePipedOutputStream((PipedOutputStream) os, basePackage, seen);
                for (String key : fileDetails.keySet()) {
                    psDetails.put(key, fileDetails.get(key)); // flatten
                }
    
            } else if (os instanceof FileOutputStream) {
                psDetails.put("special_note", "file_stream");
    
                JSONObject fileDetails = handleFileOutputStream((FileOutputStream) os, basePackage, seen);
                for (String key : fileDetails.keySet()) {
                    psDetails.put(key, fileDetails.get(key)); // flatten
                }
    
            } else {
                psDetails.put("special_note", "unknown output stream: " + os.getClass().getName());
            }
    
        } catch (Exception e) {
            psDetails.put("error", e.toString());
        }
    
        return psDetails;
    }
    

    private static JSONObject handlePipedInputStream(PipedInputStream pis, String basePackage, Set<Integer> seen) {
        JSONObject pisDetails = new JSONObject();
        pisDetails.put("type", pis.getClass().getName());

        try {
            Field bufferField = PipedInputStream.class.getDeclaredField("buffer");
            bufferField.setAccessible(true);
            byte[] buffer = (byte[]) bufferField.get(pis);
            pisDetails.put("byte_array", handlePrimitiveArray(buffer, basePackage, seen));

            Field inField = PipedInputStream.class.getDeclaredField("in");
            inField.setAccessible(true);
            int inPos = inField.getInt(pis);
            pisDetails.put("in", inPos);

            Field outField = PipedInputStream.class.getDeclaredField("out");
            outField.setAccessible(true);
            int outPos = outField.getInt(pis);
            pisDetails.put("out", outPos);
            pisDetails.put("position", outPos);

            Field connectedField = PipedInputStream.class.getDeclaredField("connected");
            connectedField.setAccessible(true);
            boolean connected = connectedField.getBoolean(pis);
            pisDetails.put("connected", Boolean.toString(connected));

        } catch (Exception e) {
            pisDetails.put("error", e.toString());
        }

        return pisDetails;
    }

    private static JSONObject handlePipedOutputStream(PipedOutputStream pos, String basePackage, Set<Integer> seen) {
        JSONObject posDetails = new JSONObject();
        posDetails.put("type", pos.getClass().getName());

        try {
            Field sinkField = PipedOutputStream.class.getDeclaredField("sink");
            sinkField.setAccessible(true);
            Object sink = sinkField.get(pos);

            if (sink instanceof PipedInputStream) {
                posDetails.put("connected", Boolean.toString(true));
                JSONObject inputStreamDetails = handlePipedInputStream((PipedInputStream) sink, basePackage, seen);
                posDetails.put("sink_details", inputStreamDetails);
            } else {
                posDetails.put("connected", Boolean.toString(false));
            }

        } catch (Exception e) {
            posDetails.put("error", e.toString());
        }

        return posDetails;
    }
    
    private static JSONObject handleByteArrayInputStream(ByteArrayInputStream bis, String basePackage, Set<Integer> seen) {
        JSONObject bisDetails = new JSONObject();
        bisDetails.put("type", getTypeName(bis, basePackage)); 
        Class<?> bisClass = bis.getClass();
        try {
            Field bufField = bisClass.getDeclaredField("buf");
            bufField.setAccessible(true);
            byte[] byteArray = (byte[]) bufField.get(bis);
            bisDetails.put("byte_array", handlePrimitiveArray(byteArray, basePackage, seen));

            Field posField = bisClass.getDeclaredField("pos");
            posField.setAccessible(true);
            int position = posField.getInt(bis);
            bisDetails.put("position", position);
        } catch (Exception e) {
            e.printStackTrace();
        }
        return bisDetails;
    }

    private static JSONObject handleByteArrayOutputStream(ByteArrayOutputStream bos, String basePackage, Set<Integer> seen) {
        JSONObject bosDetails = new JSONObject();
        bosDetails.put("type", getTypeName(bos, basePackage)); 
        Class<?> bosClass = bos.getClass();
        try {
            Field bufField = bosClass.getDeclaredField("buf");
            bufField.setAccessible(true);
            byte[] byteArray = (byte[]) bufField.get(bos);
            bosDetails.put("byte_array", handlePrimitiveArray(byteArray, basePackage, seen));
    
            Field countField = bosClass.getDeclaredField("count");
            countField.setAccessible(true);
            int count = countField.getInt(bos);
            bosDetails.put("size", count);
        } catch (Exception e) {
            e.printStackTrace();
        }
        return bosDetails;
    }

    public static JSONObject handleFileOutputStream(FileOutputStream fos, String basePackage, Set<Integer> seen) {
        JSONObject fosDetails = new JSONObject();
        fosDetails.put("type", fos.getClass().getName());
        
        try {
            Field pathField = FileOutputStream.class.getDeclaredField("path");
            pathField.setAccessible(true);
            String filePath = (String) pathField.get(fos);

            if (filePath == null) {
                // descriptor-backed stream (process pipe, System.out/err, socket): not seekable, no path
                fosDetails.put("special_note", "fd_stream");
                Object fdObj = readField(fos, FileOutputStream.class, "fd");
                Object fd = fdObj != null ? readField(fdObj, java.io.FileDescriptor.class, "fd") : null;
                fosDetails.put("fd", fd != null ? fd : JSONObject.NULL);
                fosDetails.put("file_path", JSONObject.NULL);
                return fosDetails;
            }
            fosDetails.put("file_path", filePath);

            try {
                long position = fos.getChannel().position();
                fosDetails.put("position", position);
                long fileSize = fos.getChannel().size();
                fosDetails.put("file_size", fileSize);
            } catch (Throwable t) {
                fosDetails.put("position", 0);
                fosDetails.put("file_size", new java.io.File(filePath).length());
                fosDetails.put("channel_error", t.toString());
            }

        } catch (Exception e) {
            fosDetails.put("error", e.toString());
        }
        return fosDetails;
    }

    private static JSONObject handleInputStreamReader(InputStreamReader reader, String basePackage, Set<Integer> seen) {
        JSONObject readerDetails = new JSONObject();
        readerDetails.put("type", reader.getClass().getName());
    
        try {
            String encoding = reader.getEncoding();
            readerDetails.put("encoding", encoding);
    
            Field lockField = Reader.class.getDeclaredField("lock");
            lockField.setAccessible(true);
            Object lock = lockField.get(reader);
    
            if (lock == System.in) {
                readerDetails.put("special_note", "System.in");
    
            } else if (lock instanceof ByteArrayInputStream) {
                readerDetails.put("special_note", "byte_stream");
                JSONObject byteDetails = handleByteArrayInputStream((ByteArrayInputStream) lock, basePackage, seen);
                readerDetails.put("byte_stream", byteDetails);
    
            } else if (lock instanceof FileInputStream) {
                readerDetails.put("special_note", "file_stream");
                JSONObject fileDetails = handleFileInputStream((FileInputStream) lock, basePackage, seen);
                readerDetails.put("file_stream", fileDetails);
    
            } else {
                readerDetails.put("special_note", "unknown stream type: " + lock.getClass().getName());
            }
    
        } catch (Exception e) {
            readerDetails.put("error", e.toString());
        }
    
        return readerDetails;
    }

    private static JSONObject handleOutputStreamWriter(OutputStreamWriter writer, String basePackage, Set<Integer> seen) {
        JSONObject writerDetails = new JSONObject();
        writerDetails.put("type", writer.getClass().getName());
    
        try {
            String encoding = writer.getEncoding();
            writerDetails.put("encoding", encoding);
    
            Field lockField = Writer.class.getDeclaredField("lock");
            lockField.setAccessible(true);
            Object lock = lockField.get(writer);
    
            if (lock == System.out) {
                writerDetails.put("special_note", "System.out");
    
            } else if (lock == System.err) {
                writerDetails.put("special_note", "System.err");
    
            } else if (lock instanceof ByteArrayOutputStream) {
                writerDetails.put("special_note", "byte_stream");
                JSONObject byteDetails = handleByteArrayOutputStream((ByteArrayOutputStream) lock, basePackage, seen);
                writerDetails.put("byte_stream", byteDetails);
    
            } else if (lock instanceof FileOutputStream) {
                writerDetails.put("special_note", "file_stream");
                JSONObject fileDetails = handleFileOutputStream((FileOutputStream) lock, basePackage, seen);
                writerDetails.put("file_stream", fileDetails);
    
            } else {
                writerDetails.put("special_note", "unknown stream type: " + lock.getClass().getName());
            }
    
        } catch (Exception e) {
            writerDetails.put("error", e.toString());
        }
    
        return writerDetails;
    }
    
    

    public static JSONObject handleFileInputStream(FileInputStream fis, String basePackage, Set<Integer> seen) {
        JSONObject fisDetails = new JSONObject();
        fisDetails.put("type", fis.getClass().getName());
        
        try {
            Field pathField = FileInputStream.class.getDeclaredField("path");
            pathField.setAccessible(true);
            String filePath = (String) pathField.get(fis);

            if (filePath == null) {
                // descriptor-backed stream (process pipe, System.in, socket): not seekable, no path
                fisDetails.put("special_note", fis == System.in ? "System.in" : "fd_stream");
                Object fdObj = readField(fis, FileInputStream.class, "fd");
                Object fd = fdObj != null ? readField(fdObj, java.io.FileDescriptor.class, "fd") : null;
                fisDetails.put("fd", fd != null ? fd : JSONObject.NULL);
                fisDetails.put("file_path", JSONObject.NULL);
                try { fisDetails.put("available", fis.available()); } catch (Throwable t) { /* ignore */ }
                return fisDetails;
            }
            fisDetails.put("file_path", filePath);

            try {
                long position = fis.getChannel().position();
                fisDetails.put("position", position);
                long fileSize = fis.getChannel().size();
                fisDetails.put("file_size", fileSize);
            } catch (Throwable t) {
                fisDetails.put("position", 0);
                fisDetails.put("file_size", new java.io.File(filePath).length());
                fisDetails.put("channel_error", t.toString());
            }

        } catch (Exception e) {
            fisDetails.put("error", e.toString());
        }
        return fisDetails;
    }

    public static Duration timeUnitToDuration(TimeUnit unit) {
        switch (unit) {
            case NANOSECONDS:
                return Duration.ofNanos(1);
            case MICROSECONDS:
                return Duration.of(1_000, ChronoUnit.NANOS);
            case MILLISECONDS:
                return Duration.ofMillis(1);
            case SECONDS:
                return Duration.ofSeconds(1);
            case MINUTES:
                return Duration.ofMinutes(1);
            case HOURS:
                return Duration.ofHours(1);
            case DAYS:
                return Duration.ofDays(1);
            default:
                throw new IllegalArgumentException("Unknown TimeUnit: " + unit);
        }
    }

    public static JSONObject handleDateTime(Object obj) {
        JSONObject dateTimeDetails = new JSONObject();
        if (obj instanceof Date) {
            Date date = (Date) obj;
            dateTimeDetails.put("type", "java.util.Date");
            dateTimeDetails.put("timestamp", date.getTime() / 1000.0);
        } else if (obj instanceof Calendar) {
            Calendar cal = (Calendar) obj;
            dateTimeDetails.put("type", "java.util.Calendar");
            dateTimeDetails.put("timestamp", cal.getTimeInMillis() / 1000.0);
            dateTimeDetails.put("timezone", cal.getTimeZone().getID());
        } else if (obj instanceof Instant) {
            Instant instant = (Instant) obj;
            dateTimeDetails.put("type", "java.time.Instant");
            dateTimeDetails.put("timestamp", instant.getEpochSecond() + instant.getNano() / 1_000_000_000.0);  
        } else if (obj instanceof Clock) {
            Clock clock = (Clock) obj;
            dateTimeDetails.put("type", "java.time.Clock");
            dateTimeDetails.put("instant", clock.instant().toString());
            dateTimeDetails.put("zone", clock.getZone().toString());
        } else if (obj instanceof TimeUnit) {
            TimeUnit timeUnit = (TimeUnit) obj;
            Duration duration = timeUnitToDuration(timeUnit);
            dateTimeDetails.put("type", "java.util.concurrent.TimeUnit");
            dateTimeDetails.put("seconds", duration.getSeconds());
            dateTimeDetails.put("nanos", duration.getNano());
        } else if (obj instanceof Duration) {
            Duration duration = (Duration) obj;
            dateTimeDetails.put("type", "java.time.Duration");
            dateTimeDetails.put("seconds", duration.getSeconds());
            dateTimeDetails.put("nanos", duration.getNano());
        }
        else if (obj instanceof ChronoUnit) {
            ChronoUnit unit = (ChronoUnit) obj;
            Duration duration = unit.getDuration();
            dateTimeDetails.put("type", "java.time.temporal.ChronoUnit");
            dateTimeDetails.put("seconds", duration.getSeconds());
            dateTimeDetails.put("nanos", duration.getNano());
        } else if (obj instanceof TimeZone) {
            TimeZone tz = (TimeZone) obj;
            dateTimeDetails.put("type", tz.getClass().getName()); // keep actual Java type
            dateTimeDetails.put("id", tz.getID()); // can be "America/New_York", "EST", etc.
            dateTimeDetails.put("offset", tz.getRawOffset()); // in milliseconds
            dateTimeDetails.put("dstSavings", tz.getDSTSavings()); // in milliseconds
            dateTimeDetails.put("useDaylight", tz.useDaylightTime());
        } else if (obj instanceof sun.util.calendar.ZoneInfo) {
            sun.util.calendar.ZoneInfo zone = (sun.util.calendar.ZoneInfo) obj;
            dateTimeDetails.put("type", zone.getClass().getName());
            dateTimeDetails.put("id", zone.getID());
            dateTimeDetails.put("offset", zone.getRawOffset());
            dateTimeDetails.put("dstSavings", zone.getDSTSavings());
            dateTimeDetails.put("useDaylight", zone.useDaylightTime());
        }
        return dateTimeDetails;
    }
    

    private static JSONObject handlePrintWriter(PrintWriter printWriter, String basePackage, Set<Integer> seen) {
        JSONObject printWriterDetails = new JSONObject();
        printWriterDetails.put("type", printWriter.getClass().getName());
    
        try {
            Field outField = PrintWriter.class.getDeclaredField("out");
            outField.setAccessible(true);
            Object underlyingWriter = outField.get(printWriter);
    
            if (underlyingWriter instanceof BufferedWriter) {
                Field bufferedOutField = BufferedWriter.class.getDeclaredField("out");
                bufferedOutField.setAccessible(true);
                Object bufferedInnerWriter = bufferedOutField.get(underlyingWriter);
    
                if (bufferedInnerWriter instanceof OutputStreamWriter) {
                    Field lockField = Writer.class.getDeclaredField("lock");
                    lockField.setAccessible(true);
                    Object lockObject = lockField.get(bufferedInnerWriter);
    
                    if (lockObject == System.out) {
                        printWriterDetails.put("special_note", "System.out");
                    } else if (lockObject == System.err) {
                        printWriterDetails.put("special_note", "System.err");
                    } else if (lockObject instanceof ByteArrayOutputStream) {
                        printWriter.flush();
                        printWriterDetails.put("special_note", "byte_stream");
                        printWriterDetails.put("byte_stream", handleByteArrayOutputStream((ByteArrayOutputStream) lockObject, basePackage, seen));
                    }
                } else if (bufferedInnerWriter instanceof StringWriter) {
                    StringWriter stringWriter = (StringWriter) bufferedInnerWriter;
                    printWriterDetails.put("content", stringWriter.toString());
                    printWriterDetails.put("position", stringWriter.getBuffer().length());
                } else {
                    throw new Exception("Unsupported writer type: " + bufferedInnerWriter.getClass().getName());
                }
                return printWriterDetails;
            }
    
            if (underlyingWriter instanceof StringWriter) {
                StringWriter stringWriter = (StringWriter) underlyingWriter;
                printWriterDetails.put("content", stringWriter.toString());
                printWriterDetails.put("position", stringWriter.getBuffer().length());
            } else {
                throw new Exception("Unsupported writer type: " + underlyingWriter.getClass().getName());
            }
    
        } catch (Exception e) {
            e.printStackTrace();
        }
    
        return printWriterDetails;
    }

    public static JSONObject handleMatcher(Matcher matcher, String basePackage, Set<Integer> seen) {
        JSONObject matcherDetails = new JSONObject();
        matcherDetails.put("type", matcher.getClass().getName());

        String inputString = "";
        try {
            Field textField = Matcher.class.getDeclaredField("text");
            textField.setAccessible(true);
            CharSequence inputText = (CharSequence) textField.get(matcher);
            inputString = inputText.toString();
        } catch (Exception e) {
            e.printStackTrace();
        }
         
        String patternString = matcher.pattern().pattern();
        int regionStart = matcher.regionStart();
        int regionEnd = matcher.regionEnd();

        matcherDetails.put("input_str", inputString);
        matcherDetails.put("pattern_str", patternString);
        matcherDetails.put("region_start", regionStart);
        matcherDetails.put("region_end", regionEnd);

        return matcherDetails;
    }

    public static JSONObject handleBitSet(BitSet bitSet, String basePackage, Set<Integer> seen) {
        JSONObject bitSetDetails = new JSONObject();
        bitSetDetails.put("type", bitSet.getClass().getName());
        JSONArray jsonArray = new JSONArray();
        int length = bitSet.length();
        for (int i = 0; i < length; i++) {
            jsonArray.put(new JSONObject(customToString(bitSet.get(i), seen)));
        }
        bitSetDetails.put("collection_elements", jsonArray);
        return bitSetDetails;
    }


    // -----------------------------------------------------------------------------------------------------------------
    // Serialization of java.io / java.nio / java.lang.Process / java.util.concurrent types.
    //
    // `handleExtendedLibraryObject` is consulted first by both dispatch sites (top-level objects and field values) and
    // returns null when the object is not one of the newly covered types, so the pre-existing handlers keep their
    // behavior.  Inner streams/readers/writers are resolved recursively through `handleAnyInputStream`,
    // `handleAnyOutputStream`, `handleAnyReader`, `handleAnyWriter`, so wrappers over wrappers (e.g. a DataInputStream
    // over a BufferedInputStream over a process pipe) no longer fall into the "unknown" bucket.
    // -----------------------------------------------------------------------------------------------------------------
    private static Object readField(Object target, Class<?> declaringClass, String name) {
        try {
            Field f = declaringClass.getDeclaredField(name);
            f.setAccessible(true);
            return f.get(target);
        } catch (Throwable t) {
            return null;
        }
    }

    private static Object readFieldAnywhere(Object target, String name) {
        Class<?> c = target.getClass();
        while (c != null) {
            try {
                Field f = c.getDeclaredField(name);
                f.setAccessible(true);
                return f.get(target);
            } catch (Throwable t) {
                c = c.getSuperclass();
            }
        }
        return null;
    }

    private static JSONObject handleExtendedLibraryObject(Object value, String basePackage, Set<Integer> seen) {
        if (value == null) {
            return null;
        }
        try {
            if (value instanceof java.text.DecimalFormat) {
                JSONObject d = new JSONObject();
                d.put("type", value.getClass().getName());
                d.put("pattern", ((java.text.DecimalFormat) value).toPattern());
                d.put("special_note", "decimal_format");
                return d;
            } else if (value instanceof java.text.SimpleDateFormat) {
                JSONObject d = new JSONObject();
                d.put("type", value.getClass().getName());
                d.put("pattern", ((java.text.SimpleDateFormat) value).toPattern());
                d.put("special_note", "date_format");
                return d;
            } else if (value instanceof java.text.Format) {
                JSONObject d = new JSONObject();
                d.put("type", value.getClass().getName());
                d.put("value", value.toString());
                d.put("special_note", "text_format");
                return d;
            } else if (value.getClass() == Object.class) {
                JSONObject d = new JSONObject();
                d.put("type", "java.lang.Object");
                d.put("special_note", "plain_object");
                d.put("memory_address", System.identityHashCode(value));
                return d;
            } else if (value instanceof java.nio.file.Path) {
                return handlePath((java.nio.file.Path) value);
            } else if (value instanceof java.nio.charset.Charset) {
                JSONObject d = new JSONObject();
                d.put("type", "java.nio.charset.Charset");
                d.put("value", ((java.nio.charset.Charset) value).name());
                return d;
            } else if (value instanceof java.nio.ByteBuffer) {
                return handleByteBuffer((java.nio.ByteBuffer) value, basePackage, seen);
            } else if ((value instanceof java.nio.IntBuffer) || (value instanceof java.nio.LongBuffer) || (value instanceof java.nio.ShortBuffer)
                    || (value instanceof java.nio.FloatBuffer) || (value instanceof java.nio.DoubleBuffer)) {
                return handleNumericBuffer((java.nio.Buffer) value, basePackage, seen);
            } else if (value instanceof java.io.CharArrayReader) {
                return handleCharArrayReader((java.io.CharArrayReader) value);
            } else if (value instanceof java.io.CharArrayWriter) {
                JSONObject d = new JSONObject();
                d.put("type", value.getClass().getName());
                String content = value.toString();
                d.put("content", content);
                d.put("position", content.length());
                return d;
            } else if (value instanceof java.io.BufferedWriter) {
                return handleAnyWriter((Writer) value, basePackage, seen, 0);
            } else if (value instanceof java.io.FilterReader) {
                return handleAnyReader((Reader) value, basePackage, seen, 0);
            } else if (value instanceof java.io.FilterWriter) {
                return handleAnyWriter((Writer) value, basePackage, seen, 0);
            } else if (value instanceof java.io.SequenceInputStream) {
                return handleAnyInputStream((InputStream) value, basePackage, seen, 0);
            } else if (value instanceof java.io.RandomAccessFile) {
                return handleRandomAccessFile((java.io.RandomAccessFile) value);
            } else if (value instanceof java.io.FileDescriptor) {
                JSONObject d = new JSONObject();
                d.put("type", "java.io.FileDescriptor");
                Object fd = readField(value, java.io.FileDescriptor.class, "fd");
                d.put("value", fd != null ? fd.toString() : "-1");
                return d;
            } else if (value instanceof Process) {
                return handleProcess((Process) value, basePackage, seen);
            } else if (value instanceof ProcessBuilder) {
                return handleProcessBuilder((ProcessBuilder) value, basePackage, seen);
            } else if (value instanceof Thread) {
                return handleThread((Thread) value);
            } else if (value instanceof java.util.concurrent.atomic.AtomicBoolean) {
                JSONObject d = new JSONObject();
                d.put("type", "java.util.concurrent.atomic.AtomicBoolean");
                d.put("value", Boolean.toString(((java.util.concurrent.atomic.AtomicBoolean) value).get()));
                return d;
            } else if (value instanceof java.util.concurrent.atomic.AtomicReference) {
                JSONObject d = new JSONObject();
                d.put("type", "java.util.concurrent.atomic.AtomicReference");
                Object referent = ((java.util.concurrent.atomic.AtomicReference<?>) value).get();
                d.put("referent", referent != null ? new JSONObject(customToString(referent, seen)) : JSONObject.NULL);
                return d;
            } else if (value instanceof java.util.concurrent.locks.Lock || value instanceof java.util.concurrent.locks.ReadWriteLock) {
                JSONObject d = new JSONObject();
                d.put("type", value.getClass().getName());
                d.put("lock_class", value.getClass().getName());
                if (value instanceof java.util.concurrent.locks.ReentrantLock) {
                    d.put("locked", ((java.util.concurrent.locks.ReentrantLock) value).isLocked());
                }
                return d;
            } else if (value instanceof java.util.Optional) {
                JSONObject d = new JSONObject();
                d.put("type", "java.util.Optional");
                java.util.Optional<?> opt = (java.util.Optional<?>) value;
                d.put("present", opt.isPresent());
                d.put("referent", opt.isPresent() ? new JSONObject(customToString(opt.get(), seen)) : JSONObject.NULL);
                return d;
            } else if (value instanceof Map.Entry && !(value instanceof Map)) {
                JSONObject d = new JSONObject();
                d.put("type", "java.util.Map$Entry");
                Map.Entry<?, ?> entry = (Map.Entry<?, ?>) value;
                d.put("key", entry.getKey() != null ? new JSONObject(customToString(entry.getKey(), seen)) : JSONObject.NULL);
                d.put("entry_value", entry.getValue() != null ? new JSONObject(customToString(entry.getValue(), seen)) : JSONObject.NULL);
                return d;
            } else if (value instanceof java.util.zip.Checksum && !(value instanceof CRC32)) {
                JSONObject d = new JSONObject();
                d.put("type", value.getClass().getName());
                d.put("value", Long.toString(((java.util.zip.Checksum) value).getValue()));
                return d;
            } else if (value instanceof java.util.UUID) {
                JSONObject d = new JSONObject();
                d.put("type", "java.util.UUID");
                d.put("value", value.toString());
                return d;
            } else if (value instanceof FileInputStream) {
                return handleFileInputStream((FileInputStream) value, basePackage, seen);   // fd-aware version below
            } else if (value instanceof FileOutputStream) {
                return handleFileOutputStream((FileOutputStream) value, basePackage, seen);
            } else if (value instanceof InputStream && !(value instanceof ByteArrayInputStream) && !(value instanceof PipedInputStream)
                    && !(value instanceof FilterInputStream)) {
                // any other InputStream implementation from the JDK (not an application class)
                return handleAnyInputStream((InputStream) value, basePackage, seen, 0);
            } else if (value instanceof OutputStream && !(value instanceof ByteArrayOutputStream) && !(value instanceof PipedOutputStream)
                    && !(value instanceof FilterOutputStream)) {
                return handleAnyOutputStream((OutputStream) value, basePackage, seen, 0);
            } else if (value instanceof Reader && !(value instanceof StringReader) && !(value instanceof BufferedReader)
                    && !(value instanceof InputStreamReader) && !(value instanceof PipedReader)) {
                return handleAnyReader((Reader) value, basePackage, seen, 0);
            } else if (value instanceof Writer && !(value instanceof StringWriter) && !(value instanceof PrintWriter)
                    && !(value instanceof OutputStreamWriter) && !(value instanceof PipedWriter)) {
                return handleAnyWriter((Writer) value, basePackage, seen, 0);
            }
        } catch (Throwable t) {
            JSONObject d = new JSONObject();
            d.put("type", getTypeName(value, basePackage));
            d.put("value", String.valueOf(value));
            d.put("serialization_error", t.toString());
            return d;
        }
        return null;
    }

    private static JSONObject handlePath(java.nio.file.Path path) {
        JSONObject d = new JSONObject();
        d.put("type", "java.nio.file.Path");
        d.put("value", path.toString());
        d.put("absolute", path.isAbsolute());
        return d;
    }

    private static JSONObject handleByteBuffer(java.nio.ByteBuffer buffer, String basePackage, Set<Integer> seen) {
        JSONObject d = new JSONObject();
        d.put("type", "java.nio.ByteBuffer");
        java.nio.ByteBuffer dup = buffer.duplicate();
        dup.clear();   // position 0, limit = capacity: dump the whole backing content, the reader restores position/limit
        byte[] content = new byte[buffer.limit()];
        dup.get(content, 0, buffer.limit());
        d.put("byte_array", handlePrimitiveArray(content, basePackage, seen));
        d.put("size", buffer.limit());
        d.put("position", buffer.position());
        d.put("limit", buffer.limit());
        d.put("capacity", buffer.capacity());
        d.put("byte_order", buffer.order().toString());
        d.put("direct", buffer.isDirect());
        d.put("read_only", buffer.isReadOnly());
        return d;
    }

    private static JSONObject handleNumericBuffer(java.nio.Buffer buffer, String basePackage, Set<Integer> seen) {
        JSONObject d = new JSONObject();
        JSONArray elements = new JSONArray();
        String type;
        if (buffer instanceof java.nio.IntBuffer) {
            type = "java.nio.IntBuffer";
            java.nio.IntBuffer b = ((java.nio.IntBuffer) buffer).duplicate(); b.clear();
            for (int i = 0; i < buffer.limit(); i++) { elements.put(new JSONObject(customToString(b.get(i), seen))); }
        } else if (buffer instanceof java.nio.LongBuffer) {
            type = "java.nio.LongBuffer";
            java.nio.LongBuffer b = ((java.nio.LongBuffer) buffer).duplicate(); b.clear();
            for (int i = 0; i < buffer.limit(); i++) { elements.put(new JSONObject(customToString(b.get(i), seen))); }
        } else if (buffer instanceof java.nio.ShortBuffer) {
            type = "java.nio.ShortBuffer";
            java.nio.ShortBuffer b = ((java.nio.ShortBuffer) buffer).duplicate(); b.clear();
            for (int i = 0; i < buffer.limit(); i++) { elements.put(new JSONObject(customToString(b.get(i), seen))); }
        } else if (buffer instanceof java.nio.FloatBuffer) {
            type = "java.nio.FloatBuffer";
            java.nio.FloatBuffer b = ((java.nio.FloatBuffer) buffer).duplicate(); b.clear();
            for (int i = 0; i < buffer.limit(); i++) { elements.put(new JSONObject(customToString(b.get(i), seen))); }
        } else {
            type = "java.nio.DoubleBuffer";
            java.nio.DoubleBuffer b = ((java.nio.DoubleBuffer) buffer).duplicate(); b.clear();
            for (int i = 0; i < buffer.limit(); i++) { elements.put(new JSONObject(customToString(b.get(i), seen))); }
        }
        d.put("type", type);
        d.put("collection_elements", elements);
        d.put("position", buffer.position());
        d.put("limit", buffer.limit());
        d.put("capacity", buffer.capacity());
        return d;
    }

    private static JSONObject handleCharArrayReader(java.io.CharArrayReader reader) {
        JSONObject d = new JSONObject();
        d.put("type", reader.getClass().getName());
        Object buf = readField(reader, java.io.CharArrayReader.class, "buf");
        Object pos = readField(reader, java.io.CharArrayReader.class, "pos");
        Object count = readField(reader, java.io.CharArrayReader.class, "count");
        if (buf instanceof char[]) {
            int n = count instanceof Integer ? (Integer) count : ((char[]) buf).length;
            d.put("content", new String((char[]) buf, 0, Math.min(n, ((char[]) buf).length)));
            d.put("position", pos instanceof Integer ? (Integer) pos : 0);
        } else {
            d.put("content", "");
            d.put("position", 0);
        }
        return d;
    }

    private static JSONObject handleRandomAccessFile(java.io.RandomAccessFile raf) {
        JSONObject d = new JSONObject();
        d.put("type", "java.io.RandomAccessFile");
        Object path = readField(raf, java.io.RandomAccessFile.class, "path");
        d.put("file_path", path != null ? path.toString() : JSONObject.NULL);
        try {
            d.put("position", raf.getFilePointer());
            d.put("file_size", raf.length());
        } catch (Throwable t) {
            d.put("error", t.toString());
        }
        return d;
    }

    private static JSONObject handleProcess(Process process, String basePackage, Set<Integer> seen) {
        JSONObject d = new JSONObject();
        d.put("type", "java.lang.Process");
        d.put("process_class", process.getClass().getName());
        Object pid = readFieldAnywhere(process, "pid");
        d.put("pid", pid != null ? pid : JSONObject.NULL);
        boolean alive = process.isAlive();
        d.put("alive", alive);
        if (!alive) {
            try { d.put("exit_value", process.exitValue()); } catch (Throwable t) { d.put("exit_value", JSONObject.NULL); }
        } else {
            d.put("exit_value", JSONObject.NULL);
        }
        try { d.put("stdout", handleAnyInputStream(process.getInputStream(), basePackage, seen, 0)); } catch (Throwable t) { /* ignore */ }
        try { d.put("stderr", handleAnyInputStream(process.getErrorStream(), basePackage, seen, 0)); } catch (Throwable t) { /* ignore */ }
        try { d.put("stdin", handleAnyOutputStream(process.getOutputStream(), basePackage, seen, 0)); } catch (Throwable t) { /* ignore */ }
        return d;
    }

    private static JSONObject handleProcessBuilder(ProcessBuilder pb, String basePackage, Set<Integer> seen) {
        JSONObject d = new JSONObject();
        d.put("type", "java.lang.ProcessBuilder");
        d.put("command", handleCollection(pb.command(), basePackage, seen));
        d.put("directory", pb.directory() != null ? pb.directory().toString() : JSONObject.NULL);
        d.put("redirect_error_stream", pb.redirectErrorStream());
        return d;
    }

    private static JSONObject handleThread(Thread thread) {
        JSONObject d = new JSONObject();
        d.put("type", "java.lang.Thread");
        d.put("thread_class", thread.getClass().getName());
        d.put("name", thread.getName());
        d.put("daemon", thread.isDaemon());
        d.put("alive", thread.isAlive());
        d.put("state", thread.getState().toString());
        d.put("priority", thread.getPriority());
        return d;
    }

    /** Recursive, wrapper-aware serialization of any java.io.InputStream. */
    private static JSONObject handleAnyInputStream(InputStream in, String basePackage, Set<Integer> seen, int depth) {
        JSONObject d = new JSONObject();
        if (in == null) {
            d.put("type", "null");
            return d;
        }
        d.put("type", in.getClass().getName());
        if (depth > 8) {
            d.put("stream_type", "unknown");
            d.put("stream_class", in.getClass().getName());
            return d;
        }
        try {
            if (in instanceof ByteArrayInputStream) {
                return handleByteArrayInputStream((ByteArrayInputStream) in, basePackage, seen);
            } else if (in instanceof FileInputStream) {
                return handleFileInputStream((FileInputStream) in, basePackage, seen);
            } else if (in instanceof PipedInputStream) {
                return handlePipedInputStream((PipedInputStream) in, basePackage, seen);
            } else if (in instanceof java.io.SequenceInputStream) {
                Object current = readField(in, java.io.SequenceInputStream.class, "in");
                d.put("stream_type", current instanceof InputStream ? "sequence" : "unknown");
                if (current instanceof InputStream) {
                    d.put("stream_details", handleAnyInputStream((InputStream) current, basePackage, seen, depth + 1));
                }
                return d;
            } else if (in instanceof FilterInputStream) {
                Object inner = readField(in, FilterInputStream.class, "in");
                if (in instanceof java.io.PushbackInputStream) {
                    Object buf = readField(in, java.io.PushbackInputStream.class, "buf");
                    Object pos = readField(in, java.io.PushbackInputStream.class, "pos");
                    if (buf instanceof byte[] && pos instanceof Integer) {
                        byte[] b = (byte[]) buf; int p = (Integer) pos;
                        d.put("pushback_bytes", handlePrimitiveArray(Arrays.copyOfRange(b, p, b.length), basePackage, seen));
                    }
                }
                if (inner instanceof InputStream) {
                    JSONObject innerDetails = handleAnyInputStream((InputStream) inner, basePackage, seen, depth + 1);
                    d.put("stream_type", innerDetails.has("file_path") ? "file_stream" : "byte_stream");
                    d.put("stream_details", innerDetails);
                } else {
                    d.put("stream_type", "unknown");
                    d.put("stream_class", inner != null ? inner.getClass().getName() : "null");
                }
                return d;
            } else if (in == System.in) {
                d.put("special_note", "System.in");
                return d;
            } else {
                d.put("stream_type", "unknown");
                d.put("stream_class", in.getClass().getName());
                try { d.put("available", in.available()); } catch (Throwable t) { /* ignore */ }
                return d;
            }
        } catch (Throwable t) {
            d.put("error", t.toString());
            return d;
        }
    }

    /** Recursive, wrapper-aware serialization of any java.io.OutputStream. */
    private static JSONObject handleAnyOutputStream(OutputStream out, String basePackage, Set<Integer> seen, int depth) {
        JSONObject d = new JSONObject();
        if (out == null) {
            d.put("type", "null");
            return d;
        }
        d.put("type", out.getClass().getName());
        if (depth > 8) {
            d.put("stream_type", "unknown");
            d.put("stream_class", out.getClass().getName());
            return d;
        }
        try {
            if (out instanceof ByteArrayOutputStream) {
                return handleByteArrayOutputStream((ByteArrayOutputStream) out, basePackage, seen);
            } else if (out instanceof FileOutputStream) {
                return handleFileOutputStream((FileOutputStream) out, basePackage, seen);
            } else if (out instanceof PipedOutputStream) {
                return handlePipedOutputStream((PipedOutputStream) out, basePackage, seen);
            } else if (out instanceof PrintStream) {
                if (out == System.out) { d.put("special_note", "System.out"); return d; }
                if (out == System.err) { d.put("special_note", "System.err"); return d; }
                return handlePrintStream((PrintStream) out, basePackage, seen);
            } else if (out instanceof FilterOutputStream) {
                Object inner = readField(out, FilterOutputStream.class, "out");
                if (inner instanceof OutputStream) {
                    JSONObject innerDetails = handleAnyOutputStream((OutputStream) inner, basePackage, seen, depth + 1);
                    d.put("stream_type", innerDetails.has("file_path") ? "file_stream" : "byte_stream");
                    d.put("stream_details", innerDetails);
                } else {
                    d.put("stream_type", "unknown");
                    d.put("stream_class", inner != null ? inner.getClass().getName() : "null");
                }
                return d;
            } else {
                d.put("stream_type", "unknown");
                d.put("stream_class", out.getClass().getName());
                return d;
            }
        } catch (Throwable t) {
            d.put("error", t.toString());
            return d;
        }
    }

    /** Recursive, wrapper-aware serialization of any java.io.Reader; payload uses the StringIO/BufferedReader shapes. */
    private static JSONObject handleAnyReader(Reader reader, String basePackage, Set<Integer> seen, int depth) {
        JSONObject d = new JSONObject();
        if (reader == null) {
            d.put("type", "null");
            return d;
        }
        d.put("type", reader.getClass().getName());
        if (depth > 8) {
            d.put("special_note", "unknown reader: " + reader.getClass().getName());
            return d;
        }
        try {
            JSONObject inner = null;
            if (reader instanceof StringReader) {
                inner = handleStringReader((StringReader) reader, basePackage, seen);
                inner.put("content", inner.opt("value"));
            } else if (reader instanceof java.io.CharArrayReader) {
                inner = handleCharArrayReader((java.io.CharArrayReader) reader);
            } else if (reader instanceof BufferedReader) {
                inner = handleBufferedReader((BufferedReader) reader, basePackage, seen);
            } else if (reader instanceof InputStreamReader) {
                inner = handleInputStreamReader((InputStreamReader) reader, basePackage, seen);
            } else if (reader instanceof PipedReader) {
                inner = handlePipedReader((PipedReader) reader, basePackage, seen);
            } else if (reader instanceof java.io.FilterReader) {
                Object wrapped = readField(reader, java.io.FilterReader.class, "in");
                if (reader instanceof java.io.PushbackReader) {
                    Object buf = readField(reader, java.io.PushbackReader.class, "buf");
                    Object pos = readField(reader, java.io.PushbackReader.class, "pos");
                    if (buf instanceof char[] && pos instanceof Integer) {
                        char[] b = (char[]) buf; int p = (Integer) pos;
                        d.put("pushback_chars", new String(b, p, b.length - p));
                    }
                }
                inner = wrapped instanceof Reader ? handleAnyReader((Reader) wrapped, basePackage, seen, depth + 1) : null;
            }
            if (inner != null) {
                for (String key : inner.keySet()) {
                    if (!key.equals("type") && !key.equals("memory_address")) {
                        d.put(key, inner.get(key));
                    }
                }
                d.put("inner_reader_class", inner.optString("type"));
            } else {
                d.put("special_note", "unknown reader: " + reader.getClass().getName());
            }
        } catch (Throwable t) {
            d.put("error", t.toString());
        }
        return d;
    }

    /** Recursive, wrapper-aware serialization of any java.io.Writer; payload uses the PrintWriter/StringIO shapes. */
    private static JSONObject handleAnyWriter(Writer writer, String basePackage, Set<Integer> seen, int depth) {
        JSONObject d = new JSONObject();
        if (writer == null) {
            d.put("type", "null");
            return d;
        }
        d.put("type", writer.getClass().getName());
        if (depth > 8) {
            d.put("special_note", "unknown writer: " + writer.getClass().getName());
            return d;
        }
        try {
            JSONObject inner = null;
            if (writer instanceof StringWriter) {
                StringWriter sw = (StringWriter) writer;
                inner = new JSONObject();
                inner.put("content", sw.toString());
                inner.put("position", sw.getBuffer().length());
            } else if (writer instanceof java.io.CharArrayWriter) {
                inner = new JSONObject();
                String content = writer.toString();
                inner.put("content", content);
                inner.put("position", content.length());
            } else if (writer instanceof PrintWriter) {
                inner = handlePrintWriter((PrintWriter) writer, basePackage, seen);
            } else if (writer instanceof OutputStreamWriter) {
                inner = handleOutputStreamWriter((OutputStreamWriter) writer, basePackage, seen);
            } else if (writer instanceof PipedWriter) {
                inner = handlePipedWriter((PipedWriter) writer, basePackage, seen);
            } else if (writer instanceof java.io.BufferedWriter) {
                try { writer.flush(); } catch (Throwable t) { /* flushing a closed writer is harmless here */ }
                Object wrapped = readField(writer, java.io.BufferedWriter.class, "out");
                inner = wrapped instanceof Writer ? handleAnyWriter((Writer) wrapped, basePackage, seen, depth + 1) : null;
            } else if (writer instanceof java.io.FilterWriter) {
                Object wrapped = readField(writer, java.io.FilterWriter.class, "out");
                inner = wrapped instanceof Writer ? handleAnyWriter((Writer) wrapped, basePackage, seen, depth + 1) : null;
            }
            if (inner != null) {
                for (String key : inner.keySet()) {
                    if (!key.equals("type") && !key.equals("memory_address")) {
                        d.put(key, inner.get(key));
                    }
                }
                d.put("inner_writer_class", inner.optString("type"));
            } else {
                d.put("special_note", "unknown writer: " + writer.getClass().getName());
            }
        } catch (Throwable t) {
            d.put("error", t.toString());
        }
        return d;
    }

    public static String getTypeName(Object obj, String basePackage) {
        String fullTypeName = "";
        if (obj.getClass().isArray()) {
            Class<?> componentType = obj.getClass().getComponentType();
            String arrayType = componentType.getName();
            if (componentType.isPrimitive()) {
                arrayType += "[]";
            } else {
                arrayType = arrayType + "[]";
            }
            fullTypeName = arrayType;
        } else {
            fullTypeName = obj.getClass().getName();
        }
        if (fullTypeName.startsWith(basePackage)) {
            if (isTestClass(obj.getClass())) {
                return "src.test." + fullTypeName;
            } else {
                return "src.main." + fullTypeName;
            }
        }
        return fullTypeName;
    }

    @SuppressWarnings("unchecked")
    private static <T> Collection<T> getUnderlyingCollection(Iterator<T> iterator) {
        try {
            if (iterator instanceof Scanner) {
                Scanner scanner = (Scanner) iterator;
                try {
                    Field sourceField = Scanner.class.getDeclaredField("source");
                    sourceField.setAccessible(true);
                    Readable source = (Readable) sourceField.get(scanner);
                    if (source instanceof CharBuffer) {
                        CharBuffer cb = (CharBuffer) source;
                        int pos = cb.position();
                        String remaining = cb.subSequence(pos, cb.length()).toString();
                        return (Collection<T>) Arrays.asList(remaining.split(scanner.delimiter().pattern()));
                    }
                    return new ArrayList<>();

                } catch (Exception e) {
                    e.printStackTrace();
                    return new ArrayList<>();
                }
            }

            Class<?> clazz = iterator.getClass();

            // Handle List Iterators
            if (clazz.getName().matches(".*List(\\$)?(Itr|ListItr)")) {
                int index = -1;
                try {
                    Field cursorField = clazz.getDeclaredField("cursor");
                    cursorField.setAccessible(true);
                    index = (int) cursorField.get(iterator);
                } catch (NoSuchFieldException e1) {
                    try {
                        Field nextIndexField = clazz.getDeclaredField("nextIndex");
                        nextIndexField.setAccessible(true);
                        index = (int) nextIndexField.get(iterator);
                    } catch (NoSuchFieldException e2) {
                        return null;
                    }
                }
                Field this0Field = clazz.getDeclaredField("this$0");
                this0Field.setAccessible(true);
                List<T> list = (List<T>) this0Field.get(iterator);
                return list.subList(index, list.size());
            }

            // Handle HashMap$HashIterator or HashMap$EntryIterator
            if (clazz.getName().contains("HashMap$")) {
                Field nextField = clazz.getDeclaredField("next");
                nextField.setAccessible(true);
                Object nextNode = nextField.get(iterator);

                List<T> remaining = new ArrayList<>();
                while (nextNode != null) {
                    Field keyField = nextNode.getClass().getDeclaredField("key");
                    Field valueField = nextNode.getClass().getDeclaredField("value");
                    Field nextPointer = nextNode.getClass().getDeclaredField("next");

                    keyField.setAccessible(true);
                    valueField.setAccessible(true);
                    nextPointer.setAccessible(true);

                    Object key = keyField.get(nextNode);
                    Object value = valueField.get(nextNode);
                    remaining.add((T) new AbstractMap.SimpleEntry<>(key, value));

                    nextNode = nextPointer.get(nextNode);
                }
                return remaining;
            }

            // Handle HashSet
            if (clazz.getName().contains("HashSet$")) {
                Field mapField = clazz.getDeclaredField("this$0");
                mapField.setAccessible(true);

                // Try to use cursor if available
                try {
                    Set<T> set = (Set<T>) mapField.get(iterator);
                    Field cursorField = clazz.getDeclaredField("cursor");
                    cursorField.setAccessible(true);
                    int cursor = (int) cursorField.get(iterator);
                    List<T> asList = new ArrayList<>(set);
                    return asList.subList(cursor, asList.size());
                } catch (NoSuchFieldException e) {
                    return (Collection<T>) mapField.get(iterator);
                }
            }

            // Handle Arrays Iterator
            if (clazz.getName().equals("java.util.Arrays$ArrayItr")) {
                try {
                    Field arrayField = clazz.getDeclaredField("array");
                    arrayField.setAccessible(true);
                    Object[] array = (Object[]) arrayField.get(iterator);

                    Field cursorField = clazz.getDeclaredField("cursor");
                    cursorField.setAccessible(true);
                    int cursor = (int) cursorField.get(iterator);

                    List<T> list = (List<T>) Arrays.asList(array);
                    return list.subList(cursor, list.size());
                } catch (Exception e) {
                    e.printStackTrace();
                    return null;
                }
            }

            // Handle anonymous iterator produced by Spliterators.iterator
            String cname = clazz.getName();
            if (cname.contains("Spliterators$") || cname.contains("Spliterator")) {
                for (Field f : clazz.getDeclaredFields()) {
                    try {
                        f.setAccessible(true);
                        Object val = f.get(iterator);
                        if (val instanceof Spliterator) {
                            Spliterator<?> sp = (Spliterator<?>) val;

                            Collection<T> coll = extractCollectionFromSpliterator(sp);
                            if (coll != null) return coll;
                        }
                    } catch (Throwable ignoredField) {
                        // try next field
                    }
                }
            }

            if (clazz.getEnclosingClass() != null && !Modifier.isStatic(clazz.getModifiers())) {
                Field field = clazz.getDeclaredField("this$0");
                field.setAccessible(true);
                return (Collection<T>) field.get(iterator);
            }

        } catch (Exception e) {
            e.printStackTrace();
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private static <T> Collection<T> extractCollectionFromSpliterator(Spliterator<?> sp) {
        try {
            Class<?> sc = sp.getClass();
            for (Field sf : sc.getDeclaredFields()) {
                try {
                    sf.setAccessible(true);
                    Object v = sf.get(sp);
                    if (v == null) continue;

                    // common case: array-backed spliterator (OpenJDK: "a" or "array")
                    if (v.getClass().isArray()) {
                        Object[] arr = (Object[]) v;
                        int idx = findIndexField(sc, sp);
                        if (idx >= 0 && idx <= arr.length) {
                            Object[] slice = Arrays.copyOfRange(arr, idx, arr.length);
                            return (List<T>) Arrays.asList(slice);
                        } else {
                            return (Collection<T>) Arrays.asList(arr);
                        }
                    }

                    // common case: spliterator that holds the source collection/list
                    if (v instanceof Collection) {
                        Collection<?> src = (Collection<?>) v;
                        int idx = findIndexField(sc, sp);
                        if (idx >= 0 && src instanceof List) {
                            List<?> list = new ArrayList<>((List<?>) src);
                            return (Collection<T>) list.subList(idx, list.size());
                        }
                        return (Collection<T>) src;
                    }
                } catch (Throwable ignoredInner) {
                    // continue scanning fields
                }
            }
        } catch (Throwable t) {
            // ignore and return null to indicate failure
        }
        return null;
    }

    // try to locate an "index"/"cursor" field (heuristic)
    private static int findIndexField(Class<?> sc, Object instance) {
        String[] candidates = new String[] {"index", "cursor", "start", "origin", "pos", "nextIndex", "est"};
        for (String name : candidates) {
            try {
                Field idxF = sc.getDeclaredField(name);
                idxF.setAccessible(true);
                Object idxVal = idxF.get(instance);
                if (idxVal instanceof Integer) return (Integer) idxVal;
                if (idxVal instanceof Long) return (int) ((Long) idxVal).longValue();
            } catch (NoSuchFieldException | IllegalAccessException ignored) {
                // try next candidate
            }
        }
        return -1;
    }


    public static boolean isTestClass(Class<?> clazz) {
        String path = clazz.getProtectionDomain()
                        .getCodeSource()
                        .getLocation()
                        .getPath();
        if (path.contains("test-classes")) {
            return true;
        }
        return false;
    }

    public static String customToString(Object obj, Set<Integer> seen) {
        return customToJSONObject(obj, seen).toString();
    }
}
