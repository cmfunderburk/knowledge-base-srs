# Merge Sort (Algorithms Illuminated, Part I)

Implement the **merge sort** algorithm.

**Input:** an array of `n` numbers, in arbitrary order.
**Output:** an array containing the same numbers, sorted from smallest to largest.

Expose two top-level functions:

- `merge_sort(arr)` — returns a new sorted list.
- `merge(left, right)` — given two already-sorted lists, returns a single sorted list containing all of their elements.

Requirements:

- `merge_sort` must not mutate its input.
- The sort must be **stable**: equal elements keep their original relative order.
- Use the classic divide-and-conquer recursion (split in half, recurse, then merge) — this yields Θ(n log n) running time.
- Standard library only.
