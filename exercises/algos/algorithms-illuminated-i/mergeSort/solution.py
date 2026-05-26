# Problem: Sorting
# Input: An array of n numbers, in arbitrary order.
# Output: An array of the same numbers, sorted from smallest to largest.
#
# Algorithm: Merge Sort

def merge_sort(arr):
    # If array contains >= 1 element, then it's already "sorted."
    if len(arr) <= 1:
        return arr
    
    pivot = len(arr) // 2
    leftArray = merge_sort(arr[:pivot])
    rightArray = merge_sort(arr[pivot:])
    return merge(leftArray, rightArray)


def merge(left, right):
    i = j = 0
    sortedArray = []

    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            sortedArray.append(left[i])
            i += 1
        else:
            sortedArray.append(right[j])
            j += 1

    sortedArray.extend(left[i:])
    sortedArray.extend(right[j:])
    return sortedArray
