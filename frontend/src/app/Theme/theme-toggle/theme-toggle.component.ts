import { Component, ChangeDetectionStrategy } from '@angular/core';
import { ThemeService } from '../../Core/services/theme.service';

@Component({
  selector: 'app-theme-toggle',
  standalone: true,
  templateUrl: './theme-toggle.component.html',
  styleUrls: ['./theme-toggle.component.css'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ThemeToggleComponent {
  constructor(public theme: ThemeService) {}

  sunIcon = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true">
  <path d="M6.76 4.84l-1.8-1.79L3.17 4.84l1.79 1.79 1.8-1.79zM1 13h3v-2H1v2zm10 10h2v-3h-2v3zm7.04-19.95l-1.79 1.79 1.8 1.79 1.79-1.79-1.8-1.79zM20 11v2h3v-2h-3zM6.76 19.16l-1.8 1.79 1.8 1.79 1.79-1.79-1.79-1.79zM17.24 19.16l1.79 1.79 1.8-1.79-1.8-1.79-1.79 1.79zM12 6a6 6 0 100 12 6 6 0 000-12z"/>
</svg>`.trim();

  moonIcon = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true">
  <path d="M21.75 14.5A9.75 9.75 0 1110.5 2.25a8 8 0 0011.25 12.25z"/>
</svg>`.trim();

  onToggle(): void {
    this.theme.toggle();
  }
}
