import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { segments } from '../../src/voice'

// The server cuts a sentence into lines the same way (src/flashtap/voice.py `segments`, tests/unit/test_voice.py reads
// this file too): a clip is found by its line's text, so the two must agree to the character.
const fixture = JSON.parse(readFileSync(new URL('../fixtures/voice-segments.json', import.meta.url), 'utf8')) as { cases: [string, string[]][] }

describe('voice segments', () => {
  it.each(fixture.cases)('cuts %j as the server does', (text, want) => {
    expect(segments(text)).toEqual(want)
  })
})
