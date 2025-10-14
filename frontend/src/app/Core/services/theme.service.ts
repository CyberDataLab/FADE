import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { DOCUMENT, isPlatformBrowser } from '@angular/common';

export type Theme = 'light' | 'dark';
const STORAGE_KEY = 'app-theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private current: Theme = 'light';
  private readonly isBrowser: boolean;
  private storage: Storage | null = null;

  constructor(
    @Inject(PLATFORM_ID) platformId: Object,
    @Inject(DOCUMENT) private doc: Document
  ) {
    // Solo en navegador hay window/localStorage y DOM real
    this.isBrowser = isPlatformBrowser(platformId);

    if (this.isBrowser && typeof globalThis.localStorage !== 'undefined') {
      this.storage = globalThis.localStorage;
    }

    const saved = (this.storage?.getItem(STORAGE_KEY) as Theme | null) ?? 'light';
    this.applyTheme(saved); // inicializa sin tocar DOM/LS en SSR
  }

  get theme(): Theme {
    return this.current;
  }

  isDark(): boolean {
    return this.current === 'dark';
  }

  toggle(): void {
    this.setTheme(this.isDark() ? 'light' : 'dark');
  }

  setTheme(theme: Theme): void {
    this.applyTheme(theme);
  }

  private applyTheme(theme: Theme): void {
    this.current = theme;

    // En servidor no tocamos DOM ni localStorage
    if (this.isBrowser && this.doc?.documentElement) {
      this.doc.documentElement.setAttribute('data-theme', theme);
      this.storage?.setItem(STORAGE_KEY, theme);
    }
  }
}
