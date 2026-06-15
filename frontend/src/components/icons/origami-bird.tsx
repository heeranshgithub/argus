import type { SVGProps } from "react";

export function OrigamiBird({
  className,
  ...props
}: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      {...props}
    >
      <path d="M3 7 L21 5 L13 13 L21 5 L17 19 L12 14 L8 21 L13 13 Z" />
    </svg>
  );
}
