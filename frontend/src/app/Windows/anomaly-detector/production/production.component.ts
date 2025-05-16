import { Component, OnInit, Inject, PLATFORM_ID } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ScenarioService } from '../../scenario.service';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { interval,Subscription } from 'rxjs';


@Component({
  selector: 'app-production',
  imports: [CommonModule],
  templateUrl: './production.component.html',
  styleUrl: './production.component.css'
})
export class ProductionComponent implements OnInit{
  uuid: string = '';
  isPlaying = false;
  productionAnomalies: any[] = [];
  refreshSubscription!: Subscription;

  constructor(private route: ActivatedRoute, private router: Router, private scenarioService: ScenarioService, @Inject(PLATFORM_ID) private platformId: Object) {}

  ngOnInit(): void {
    this.uuid = this.route.snapshot.paramMap.get('id') || '';
    this.loadProductionAnomalies();
  }

  ngOnDestroy(): void {
    if (this.refreshSubscription) {
      this.refreshSubscription.unsubscribe();
    }
  }

  isProductionRoute(): boolean {
    const currentPath = `/dashboard/anomaly-detector/${this.uuid}/production`;
    const isActive = this.router.isActive(currentPath, true);
    return(isActive);

  }

  toggle() {
    if (this.isPlaying) {
      this.stop();
    } else {
      this.play();
    }
  }

  play() {
    this.scenarioService.playProduction(this.uuid).subscribe({
      next: () => {
        this.isPlaying = true;
        console.log('Playback started');
  
        this.loadProductionAnomalies(); // carga inicial inmediata
  
        // activa el refresco continuo
        this.refreshSubscription = interval(1000).subscribe(() => {
          if (this.isPlaying) {
            this.loadProductionAnomalies();
          }
        });
      },
      error: err => console.error('Error starting playback', err)
    });
  }
  
  stop() {
    this.scenarioService.stopProduction(this.uuid).subscribe({
      next: () => {
        this.isPlaying = false;
        console.log('Playback stopped');
  
        if (this.refreshSubscription) {
          this.refreshSubscription.unsubscribe();
        }
      },
      error: err => console.error('Error stopping playback', err)
    });
  }

  loadProductionAnomalies(): void {
    if (!this.uuid) return;
  
    this.scenarioService.getScenarioProductionAnomalyMetrics(this.uuid).subscribe({
      next: (data) => {
        // Ordenar por fecha descendente
        this.productionAnomalies = (data.metrics || []).sort(
          (a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime()
        );
      },
      error: (err) => {
        console.error("Error loading production anomalies:", err);
      }
    });
  }
  

}
