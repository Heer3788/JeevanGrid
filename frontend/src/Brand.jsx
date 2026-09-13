import React from 'react';

export function GridMark() {
  return <span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><path d="M7 6h8v8H5L7 6Zm11 0h7l2 8h-9V6ZM4 17h11v9H2l2-9Zm14 0h10l2 9H18v-9Z" fill="currentColor"/></svg></span>;
}

export default function Brand() {
  return <><GridMark/><span className="brand-name">Jeevan<span>Grid</span></span></>;
}
