'use client';
import { useCallback, useEffect, useRef, useState } from 'react';

export interface TextSelection {
  text: string;
  page: number | null;
}

export function useTextSelection(readerRootRef: React.RefObject<HTMLElement | null>) {
  const [selection, setSelection] = useState<TextSelection | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSelectionChange = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed) {
        setSelection(null);
        return;
      }
      const text = sel.toString().trim();
      if (text.length < 3) {
        setSelection(null);
        return;
      }

      // Only capture selections inside [data-reader-root]
      const root = readerRootRef.current;
      if (!root) return;
      const anchorNode = sel.anchorNode;
      if (!anchorNode || !root.contains(anchorNode)) {
        return;
      }

      // Find closest [data-page] ancestor
      let el: Node | null = anchorNode;
      let page: number | null = null;
      while (el && el !== root) {
        if (el instanceof Element) {
          const p = el.getAttribute('data-page');
          if (p) {
            page = parseInt(p, 10);
            break;
          }
        }
        el = el.parentNode;
      }

      setSelection({ text, page });
    }, 100);
  }, [readerRootRef]);

  const clearSelection = useCallback(() => {
    setSelection(null);
    window.getSelection()?.removeAllRanges();
  }, []);

  useEffect(() => {
    document.addEventListener('selectionchange', handleSelectionChange);
    return () => {
      document.removeEventListener('selectionchange', handleSelectionChange);
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [handleSelectionChange]);

  return { selection, clearSelection };
}
