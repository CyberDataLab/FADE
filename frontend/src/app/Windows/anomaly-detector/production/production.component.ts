import { Component, OnInit, Inject, PLATFORM_ID } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ScenarioService } from '../../scenario.service';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { interval,Subscription } from 'rxjs';
import JSZip from 'jszip';
import { saveAs } from 'file-saver';

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
  modalImage: string | null = null;
  hoverDirection: { [index: number]: 'up' | 'down' } = {};
  hoverPanelRef: HTMLElement | null = null;

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
  
        this.loadProductionAnomalies();
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
        this.productionAnomalies = (data.metrics || []).sort(
          (a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime()
        );
      },
      error: (err) => {
        console.error("Error loading production anomalies:", err);
      }
    });
  }

  openModal(imageUrl: string) {
    this.modalImage = imageUrl;
  }
  
  closeModal() {
    this.modalImage = null;
  }

  checkPosition(event: MouseEvent, index: number): void {
    const element = event.target as HTMLElement;
    const rect = element.getBoundingClientRect();
  
    const container = document.querySelector('.table-container') as HTMLElement;
    const containerRect = container.getBoundingClientRect();
  
    const spaceBelow = containerRect.bottom - rect.bottom;
    const threshold = 300;
  
    this.hoverDirection[index] = spaceBelow < threshold ? 'up' : 'down';
  }

  showHoverImages(event: MouseEvent, index: number): void {
    this.checkPosition(event, index);
    const target = event.currentTarget as HTMLElement;

    const panel = target.querySelector('.hover-images') as HTMLElement;
    if (panel) {
      const rect = target.getBoundingClientRect();
      panel.style.display = 'flex';
      panel.style.left = `${rect.left}px`;
  
      if (this.hoverDirection[index] === 'up') {
        panel.style.bottom = `${window.innerHeight - rect.top}px`;
        panel.style.top = 'auto';
      } else {
        panel.style.top = `${rect.bottom}px`;
        panel.style.bottom = 'auto';
      }
  
      this.hoverPanelRef = panel;
    }
  }
  
  hideHoverImages(): void {
    if (this.hoverPanelRef) {
      this.hoverPanelRef.style.display = 'none';
      this.hoverPanelRef = null;
    }
  }

  async downloadAnomalyAsZip(anomaly: any, positionFromBottom: number): Promise<void> {
    const zip = new JSZip();
  
    const details = typeof anomaly.anomaly_details === 'string'
      ? JSON.parse(anomaly.anomaly_details)
      : anomaly.anomaly_details;
  
    const indexedDetails = Object.entries(details).map(([key, value], index) => ({
      index,
      field: key,
      value
    }));
  
    const jsonContent = JSON.stringify(indexedDetails, null, 2);
    zip.file(`${this.uuid}_anomaly_details_${positionFromBottom}.json`, jsonContent);
  
    const fetchAndAddImage = async (url: string, filename: string) => {
      const response = await fetch(url);
      const blob = await response.blob();
      zip.file(filename, blob);
    };
  
    if (anomaly.local_shap_images?.length) {
      for (let i = 0; i < anomaly.local_shap_images.length; i++) {
        const imageUrl = `http://localhost:8000/media/${anomaly.local_shap_images[i]}`;
        const imageName = `shap/${this.uuid}_shap_local_${positionFromBottom}.png`;
        await fetchAndAddImage(imageUrl, imageName);
      }
    }
  
    if (anomaly.local_lime_images?.length) {
      for (let i = 0; i < anomaly.local_lime_images.length; i++) {
        const imageUrl = `http://localhost:8000/media/${anomaly.local_lime_images[i]}`;
        const imageName = `lime/${this.uuid}_lime_local_${positionFromBottom}.png`;
        await fetchAndAddImage(imageUrl, imageName);
      }
    }
  
    zip.generateAsync({ type: 'blob' }).then((content: any) => {
      saveAs(content, `scenario_${this.uuid}_anomaly_${positionFromBottom}.zip`);
    });
  }
  
  deleteAnomaly(anomalyId: number): void {
    if (confirm(`Are you sure you want to delete this anomaly? This action cannot be undone.`)) {
      this.scenarioService.deleteAnomaly(this.uuid, anomalyId).subscribe({
        next: () => {
          alert('Anomaly deleted successfully');
          this.loadProductionAnomalies();
        },
        error: (error: any) => {
          console.error('Error deleting anomaly:', error);
          alert('Error deleting anomaly');
        }
      });
    }
  }
  

}
