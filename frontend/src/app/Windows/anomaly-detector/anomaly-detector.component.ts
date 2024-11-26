import { Component, EventEmitter, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FeaturesComponent } from './features/features.component';
import { Router } from '@angular/router';
import { TimelineADComponent } from './timeline-ad/timeline-ad.component';
import { MetricsComponent } from './metrics/metrics.component';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-anomaly-detector',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    FeaturesComponent,
    TimelineADComponent,
    MetricsComponent
  ],
  templateUrl: './anomaly-detector.component.html',
  styleUrl: './anomaly-detector.component.css'
})
export class AnomalyDetectorComponent {
  selectedOptionDropdown: string | null = null;

  constructor(private router: Router) {}

  // Navegar a una subruta
  navigateTo(path: string): void {
    this.router.navigate([`/dashboard/anomaly-detector/${path}`]);
  }

  // Verificar si estás en la ruta principal
  isRootSubRoute(): boolean {
    return this.router.url === '/dashboard/anomaly-detector';
  }

  // Manejo del dropdown
  onDropdownChange(): void {
    console.log('Dropdown changed to:', this.selectedOptionDropdown);
    if (this.selectedOptionDropdown === 'new') {
      this.router.navigate(['/dashboard/anomaly-detector/new-scenario/data-source']);
    } else if (this.selectedOptionDropdown === 'import') {
      this.router.navigate(['/dashboard/anomaly-detector/import-scenario']);
    }
  }
}
