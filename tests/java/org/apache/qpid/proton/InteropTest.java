/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
package org.apache.qpid.proton;

import org.apache.qpid.proton.TestDecoder;
import org.apache.qpid.proton.ProtonFactoryLoader;
import org.apache.qpid.proton.amqp.Binary;
import org.apache.qpid.proton.amqp.Symbol;
import org.apache.qpid.proton.amqp.UnsignedByte;
import org.apache.qpid.proton.amqp.UnsignedInteger;
import org.apache.qpid.proton.amqp.UnsignedLong;
import org.apache.qpid.proton.amqp.UnsignedShort;
import org.apache.qpid.proton.amqp.messaging.AmqpValue;
import org.apache.qpid.proton.message.Message;
import org.apache.qpid.proton.message.MessageFactory;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertArrayEquals;
import org.junit.Test;
import java.lang.System;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.Vector;
import java.util.List;
import java.util.ArrayList;
import java.util.Map;
import java.util.HashMap;

public class InteropTest {

    static private File findTestsInteropDir() {
	File f = new File(System.getProperty("user.dir"));
	while (f != null && !f.getName().equals("tests"))
	    f = f.getParentFile();
	if (f != null && f.isDirectory())
	    return new File(f,"interop");
	else
	    throw new Error("Cannot find tests/interop directory");
    }

    static File testsInteropDir = findTestsInteropDir();

    byte[] getBytes(String name) throws IOException {
	File f = new File(testsInteropDir, name+".amqp");
	byte[] data = new byte[(int)f.length()];
	FileInputStream fi = new FileInputStream(f);
	assertEquals(f.length(), fi.read(data));
	fi.close();
	return data;
    }

   Message decodeMessage(String name) throws IOException {
	byte[] data = getBytes(name);
	MessageFactory mf =
	    new ProtonFactoryLoader<MessageFactory>(MessageFactory.class).loadFactory();
	Message m = mf.createMessage();
	m.decode(data, 0, data.length);
	return m;
    }

    TestDecoder createDecoder(byte[] data) {
	TestDecoder td = new TestDecoder(data);
	return td;
    }

    @Test
    public void test_primitives() throws IOException {
	TestDecoder d = createDecoder(getBytes("primitives"));
	assertEquals(true, d.readBoolean());
	assertEquals(false, d.readBoolean());
	assertEquals(d.readUnsignedByte().intValue(), 42);
	assertEquals(42, d.readUnsignedShort().intValue());
	assertEquals(-42, d.readShort().intValue());
	assertEquals(12345, d.readUnsignedInteger().intValue());
	assertEquals(-12345, d.readInteger().intValue());
	assertEquals(12345, d.readUnsignedLong().longValue());
	assertEquals(-12345, d.readLong().longValue());
	assertEquals(0.125, d.readFloat().floatValue(), 0e-10);
	assertEquals(0.125, d.readDouble().doubleValue(), 0e-10);
    }

    @Test
    public void test_strings() throws IOException {
	TestDecoder d = createDecoder(getBytes("strings"));
	assertEquals(new Binary("abc\0defg".getBytes("UTF-8")), d.readBinary());
	assertEquals("abcdefg", d.readString());
	assertEquals(Symbol.valueOf("abcdefg"), d.readSymbol());
	assertEquals(new Binary(new byte[0]), d.readBinary());
	assertEquals("", d.readString());
	assertEquals(Symbol.valueOf(""), d.readSymbol());
    }

    @Test
    public void test_described() throws IOException {
	// FIXME aconway 2013-02-18: TODO
    }

    @Test
    public void test_described_array() throws IOException {
	// FIXME aconway 2013-02-18: TODO
    }

    @Test
    public void test_arrays() throws IOException {
        TestDecoder d = createDecoder(getBytes("arrays"));

	Vector<Integer> ints = new Vector<Integer>();
	for (int i = 0; i < 100; ++i) ints.add(new Integer(i));
	assertArrayEquals(ints.toArray(), d.readArray());

	String strings[] = { "a", "b", "c" };
	assertArrayEquals(strings, d.readArray());

	// FIXME aconway 2013-02-18: NPE: bug in decoder?
        // assertArrayEquals(new Integer[0], d.readArray());
    }

    @Test
    public void test_lists() throws IOException {
        TestDecoder d = createDecoder(getBytes("lists"));
	List<Object> l = new ArrayList<Object>() {{
	    add(new Integer(32));
	    add("foo");
	    add(new Boolean(true));
	}};
	assertEquals(l, d.readList());
	l.clear();
	assertEquals(l, d.readList());
    }

    @Test
    public void test_maps() throws IOException {
        TestDecoder d = createDecoder(getBytes("maps"));
	Map map = new HashMap() {{
	    put("one", 1);
	    put("two", 2);
	    put("three", 3);
	}};
	assertEquals(map, d.readMap());
	// FIXME aconway 2013-02-18: todo
    }
    // FIXME aconway 2013-02-15: add tests for all fragments generated by
    // interop-generate
}