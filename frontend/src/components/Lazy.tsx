import { type ReactNode, useEffect, useRef, useState } from "react";

interface Props {
  children: ReactNode;
  /** Reserved height for the placeholder so the scrollbar doesn't jump. */
  minHeight?: number;
  rootMargin?: string;
}

const isMobile = () =>
  typeof window !== "undefined" && window.matchMedia("(max-width: 900px)").matches;

/** Defers mounting its children until they scroll near the viewport — but only
 *  on small screens, where a dozen sidebar panels otherwise all mount, fetch-bind
 *  and animate at once. On desktop the sidebar is its own scroll container, so it
 *  renders immediately. Once shown it stays shown, so scrolling back up never
 *  tears a panel down. */
export default function Lazy({ children, minHeight = 130, rootMargin = "350px" }: Props) {
  const [show, setShow] = useState(() => !isMobile());
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (show) return;
    if (typeof IntersectionObserver === "undefined") {
      setShow(true);
      return;
    }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShow(true);
          io.disconnect();
        }
      },
      { rootMargin },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [show, rootMargin]);

  if (show) return <>{children}</>;
  return <div ref={ref} className="lazy-ph" style={{ minHeight }} aria-hidden="true" />;
}
