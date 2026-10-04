# System patterns

Input is a blank PDF or image plus a table of field values. AcroForm rectangles are used when present. Otherwise a boxes JSON supplies the rectangles in PDF points.

Each row picks a handwriting font and jitter from a seeded palette. Scan noise is applied after the text is composited. The PDF is image-only. labels.jsonl records the field rectangle, not a tight ink box.
