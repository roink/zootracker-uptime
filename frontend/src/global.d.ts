declare module '*.css';
declare module '*.png';
declare module '*.jpg';
declare module '*.jpeg';
declare module '*.svg' {
  const src: string;
  export default src;
}

declare global {
  interface Window {
    bootstrap?: unknown;
  }
}

export {};
