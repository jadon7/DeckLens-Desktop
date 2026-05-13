# Layer Background Deduplication

## Status

Accepted

## Context

Element layering can produce duplicated pixels: a movable foreground element is
also still present in the base background, and child elements can remain baked
into larger parent element layers. Moving a foreground layer then reveals an
identical copy underneath.

Local experiments compared OpenCV Telea and torch LaMa for removing those
duplicated element pixels. OpenCV Telea was cleaner for small UI elements such
as icons and buttons, and OpenCV is already part of the product dependency set.

## Decision

- Use OpenCV Telea to repair the base background after removing selected
  foreground masks.
- When a smaller mask is mostly contained inside a larger mask, repair that child
  area out of the larger parent layer.
- Keep the child layer intact as an independent movable element.
- Do not add a new model or use torch LaMa as the default for this element
  deduplication path.

## Consequences

- Moving foreground elements should no longer reveal the same pixels in the
  background or parent layer.
- UI-style slides get faster and more stable repair than LaMa for this case.
- Large or complex photo-like masks may still need future strategy work if Telea
  repair is visibly insufficient.

## Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
