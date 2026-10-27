import {test} from 'node:test';
import assert from 'node:assert/strict';
import {formatLatencyInterval} from '../../src/td-timing.js';
test('display rounding expands bounds and never creates a midpoint or fake missing zero',()=>{
 assert.equal(formatLatencyInterval({lower_ms:5.01,upper_ms:25.01}),'5–25.1 ms');
 assert.equal(formatLatencyInterval(null),null);
 assert.equal(formatLatencyInterval({lower_ms:4,upper_ms:3}),null);
 assert.equal(formatLatencyInterval({lower_ms:0,upper_ms:Infinity}),null);
 assert.equal(formatLatencyInterval({lower_ms:'5',upper_ms:25}),null);
});
