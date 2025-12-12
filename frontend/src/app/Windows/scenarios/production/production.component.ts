// Angular core and common modules
import { Component, OnInit, Inject, PLATFORM_ID, HostListener } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { interval,Subscription } from 'rxjs';
import JSZip from 'jszip';
import { saveAs } from 'file-saver';

// Application-specific imports
import { ScenarioService } from '../../../Core/services/scenario.service';
import { PoliciesService, PolicyPayload } from '../../../Core/services/policies.service';

/**
 * @summary Manages the production view of a running scenario.
 * 
 * This component handles playback of anomaly detection in production,
 * displays anomaly metrics, allows download of local explainability images,
 * and manages user interactions with anomaly cards.
 */
@Component({
  selector: 'app-production',
  imports: [CommonModule, FormsModule],
  templateUrl: './production.component.html',
  styleUrl: './production.component.css'
})
export class ProductionComponent implements OnInit{
  /** @summary UUID of the running scenario */
  uuid: string = '';

  /** @summary Flag to indicate whether scenario is currently running */
  isPlaying = false;

  /** @summary List of anomalies detected during production */
  productionAnomalies: any[] = [];

  /** @summary Subscription handler for auto-refreshing anomaly list */
  refreshSubscription!: Subscription;

  /** @summary Image URL to be displayed in modal view */
  modalImage: string | null = null;

  /** @summary Direction to show hover panels (up/down) based on index */
  hoverDirection: { [index: number]: 'up' | 'down' } = {};

  /** @summary Reference to currently visible hover panel */
  hoverPanelRef: HTMLElement | null = null;

  /** @summary Index of currently open dropdown menu, or null if none */
  dropdownOpenIndex: number | null = null;

  /** @summary Direction to show dropdown menus (up/down) based on index */
  dropdownDirection: Record<number, 'up' | 'down'> = {};  

  /**
   * @summary Injects dependencies for routing and data services.
   * 
   * @param route ActivatedRoute to extract scenario UUID
   * @param router Angular Router for navigation
   * @param scenarioService Service for managing scenario operations
   * @param platformId Identifies if app is running in browser
   */
  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private scenarioService: ScenarioService,
    private policiesService: PoliciesService,
    @Inject(PLATFORM_ID) private platformId: Object
  ) {}

  /**
   * @summary Initializes the component and loads anomaly data.
   */
  ngOnInit(): void {
    this.uuid = this.route.snapshot.paramMap.get('id') || '';
    this.loadProductionAnomalies();
  }

  /**
   * @summary Cleans up auto-refresh subscription when component is destroyed.
   */
  ngOnDestroy(): void {
    if (this.refreshSubscription) {
      this.refreshSubscription.unsubscribe();
    }
  }

  onModeChange(): void {
    this.loadProductionAnomalies();
  }

  /**
   * @summary Verifies if current route matches the production view.
   * 
   * @returns Whether the production route is currently active
   */
  isProductionRoute(): boolean {
    const currentPath = `/dashboard/scenarios/${this.uuid}/production`;
    const isActive = this.router.isActive(currentPath, true);
    return(isActive);

  }

  /**
   * @summary Toggles production state (play/stop).
   */
  toggle() {
    if (this.isPlaying) {
      this.stop();
    } else {
      this.play();
    }
  }

  /**
   * @summary Toggle the dropdown menu for a given row
   * @param event MouseEvent from the click
   * @param idx Index of the row (counting from bottom)
   */
  toggleDropdown(event: MouseEvent, idx: number) {
    event.stopPropagation();
  
    // Simple toggle
    if (this.dropdownOpenIndex === idx) {
      this.dropdownOpenIndex = null;
      return;
    }
  
    this.dropdownOpenIndex = idx;
  
    // Calulate available space to decide menu direction
    const btn = event.currentTarget as HTMLElement;
    const rect = btn.getBoundingClientRect();
  
    // Estimaged height of the menu (4 items * ~36px + padding). If you change the number of items, adjust:
    const MENU_ESTIMATED_HEIGHT = 4 * 36 + 12;
  
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
  
    this.dropdownDirection[idx] =
      spaceBelow < MENU_ESTIMATED_HEIGHT && spaceAbove > spaceBelow ? 'up' : 'down';
  }

  /**
   * @summary Starts the scenario playback and activates data refresh loop.
   */
  play() {
    this.scenarioService.playProduction(this.uuid).subscribe({
      next: () => {
        this.isPlaying = true;
  
        // Load initial anomalies immediately
        this.loadProductionAnomalies();

        // Set up interval to refresh anomalies every second
        this.refreshSubscription = interval(1000).subscribe(() => {
          if (this.isPlaying) {
            this.loadProductionAnomalies();
          }
        });
      },
      error: err => console.error('Error starting playback', err)
    });
  }
  
  /**
   * @summary Stops the scenario playback and clears the data refresh loop.
   */
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

  /**
   * @summary Loads anomaly metrics from the backend for this scenario.
   */
  loadProductionAnomalies(): void {
    if (!this.uuid) return;
  
    this.scenarioService.getScenarioProductionAnomalyMetrics(this.uuid).subscribe({
      next: (data) => {
        // Sort anomalies by descending date
        this.productionAnomalies = (data.metrics || []).sort(
          (a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime()
        );
      },
      error: (err) => {
        console.error("Error loading production anomalies:", err);
      }
    });
  }

  /**
   * @summary Opens modal view with the selected image.
   * 
   * @param imageUrl URL of the image to display
   */
  openModal(imageUrl: string) {
    this.modalImage = imageUrl;
  }
  
  /**
   * @summary Closes the image modal.
   */
  closeModal() {
    this.modalImage = null;
  }

  /**
   * @summary Determines whether the hover panel should appear above or below the item.
   * 
   * @param event MouseEvent from hover
   * @param index Index of hovered anomaly
   */
  checkPosition(event: MouseEvent, index: number): void {
    // Calculate space below element to decide hover panel direction
    const element = event.target as HTMLElement;
    const rect = element.getBoundingClientRect();
  
    const container = document.querySelector('.table-container') as HTMLElement;
    const containerRect = container.getBoundingClientRect();
  
    const spaceBelow = containerRect.bottom - rect.bottom;
    const threshold = 300;
  
    // Set direction based on available space
    this.hoverDirection[index] = spaceBelow < threshold ? 'up' : 'down';
  }

  /**
   * @summary Shows hover panel with local explanation images.
   * 
   * @param event MouseEvent triggered by hover
   * @param index Index of the anomaly
   */
  showHoverImages(event: MouseEvent, index: number): void {
    this.checkPosition(event, index);
    const target = event.currentTarget as HTMLElement;

    const panel = target.querySelector('.hover-images') as HTMLElement;
    if (panel) {
      const rect = target.getBoundingClientRect();
      panel.style.display = 'flex';
      panel.style.left = `${rect.left}px`;
  
      // Position the hover panel above or below
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
  
  /**
   * @summary Hides the currently visible hover panel.
   */
  hideHoverImages(): void {
    if (this.hoverPanelRef) {
      this.hoverPanelRef.style.display = 'none';
      this.hoverPanelRef = null;
    }
  }

  /**
   * @summary Downloads a selected anomaly's data and images as a ZIP file.
   * 
   * @param anomaly The anomaly object to download
   * @param positionFromBottom Index used for filename context
   */
  async downloadAnomalyAsZip(anomaly: any, positionFromBottom: number): Promise<void> {
    const zip = new JSZip();

    let detailsObj: any | null = null;
    let detailsTxt: string | null = null;

    if (typeof anomaly.anomaly_details === 'string') {
      try {
        detailsObj = JSON.parse(anomaly.anomaly_details);
      } catch {
        detailsTxt = anomaly.anomaly_details;
      }
    } else {
      detailsObj = anomaly.anomaly_details ?? null;
    }

    const baseName = `${this.uuid}_anomaly_details_${positionFromBottom}`;
    if (detailsObj !== null) {
      zip.file(`${baseName}.json`, JSON.stringify(detailsObj, null, 2), {
        date: new Date(),
      });
    } else {
      zip.file(`${baseName}.txt`, detailsTxt ?? '', { date: new Date() });
    }
  
    // Helper function to fetch image and add to ZIP
    const fetchAndAddImage = async (url: string, filename: string) => {
      const response = await fetch(url);
      const blob = await response.blob();
      zip.file(filename, blob);
    };
  
    // Include SHAP local images (if any)
    if (anomaly.local_shap_images?.length) {
      for (let i = 0; i < anomaly.local_shap_images.length; i++) {
        const imageUrl = `http://localhost:8000/media/${anomaly.local_shap_images[i]}`;
        const imageName = `shap/${this.uuid}_shap_local_${positionFromBottom}.png`;
        await fetchAndAddImage(imageUrl, imageName);
      }
    }
  
    // Include LIME local images (if any)
    if (anomaly.local_lime_images?.length) {
      for (let i = 0; i < anomaly.local_lime_images.length; i++) {
        const imageUrl = `http://localhost:8000/media/${anomaly.local_lime_images[i]}`;
        const imageName = `lime/${this.uuid}_lime_local_${positionFromBottom}.png`;
        await fetchAndAddImage(imageUrl, imageName);
      }
    }

    
    // Trigger download of the ZIP
    zip.generateAsync({ type: 'blob' }).then((content: any) => {
      saveAs(content, `scenario_${this.uuid}_anomaly_${positionFromBottom}.zip`);
    });
  }
  
  /**
   * @summary Deletes a specific anomaly by its ID after confirmation.
   * 
   * @param anomalyId Unique identifier of the anomaly to delete
   */
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

  /**
   * @summary Close any open dropdown when clicking outside
   */
  @HostListener('document:click', ['$event'])
  onDocumentClick(_: MouseEvent): void {
    this.dropdownOpenIndex = null;
  }

  /**
   * @summary Handle actions triggered from the dropdown menu
   * @param action 'block_ip_src' | 'block_ip_dst' | 'block_port_src' | 'block_port_dst'
   * @param anomaly Current row anomaly object
   */
  onDropdownAction(
    action: 'block_ip_src' | 'block_ip_dst' | 'block_port_src' | 'block_port_dst',
    anomaly: any
  ): void {
    this.dropdownOpenIndex = null; // close menu

    const { src_ip, dst_ip, src_port, dst_port } = this.extractNetworkFields(anomaly);

    switch (action) {
      case 'block_ip_src': {
        const value = src_ip ?? 'unknown';

        if(value === 'None' || value === 'unknown') {
          alert('Source IP is None or unknown, cannot block.');
          return;

        }

        const payload: PolicyPayload = {
          type: 'block_ip_src',
          value: value
        };

        this.policiesService.applyPolicy(payload).subscribe({
          next: (res) => (alert(`IP ${value} blocked`)),
          error: (err) => (alert('Error applying policy'))
        });

        break;
      }
      case 'block_ip_dst': {
        const value = dst_ip ?? 'unknown';

        if(value === 'None' || value === 'unknown') {
          alert('Destination IP is None or unknown, cannot block.');
          return;
        }
        
        const payload: PolicyPayload = {
          type: 'block_ip_dst',
          value: value
        };

        this.policiesService.applyPolicy(payload).subscribe({
          next: (res) => (alert(`IP ${value} blocked`)),
          error: (err) => (alert('Error applying policy'))
        });

        break;
      }
      case 'block_port_src': {
        const value = (src_port ?? 'unknown').toString();

        if(value === '-1' || value === 'unknown') {
          alert('Source port is -1, cannot block.');
          return;
        }
        
        const payload: PolicyPayload = {
          type: 'block_port_src',
          value: value
        };

        this.policiesService.applyPolicy(payload).subscribe({
          next: (res) => (alert(`Port ${value} blocked`)),
          error: (err) => (alert('Error applying policy'))
        });

        break;
      }
      case 'block_port_dst': {
        const value = (dst_port ?? 'unknown').toString();

        if(value === '-1' || value === 'unknown') {
          alert('Source port is -1, cannot block.');
          return;
        }
        
        const payload: PolicyPayload = {
          type: 'block_port_dst',
          value: value
        };

        this.policiesService.applyPolicy(payload).subscribe({
          next: (res) => (alert(`Port ${value} blocked`)),
          error: (err) => (alert('Error applying policy'))
        });

        break;
      }
    }
  }

  /**
   * @summary Handle actions triggered from the dropdown menu
   * @param action Selected action ('block_ip' | 'block_port')
   * @param anomaly Anomaly object associated with the action
   */
  private extractNetworkFields(anomaly: any): {
    src_ip?: string; dst_ip?: string; src_port?: string | number; dst_port?: string | number;
  } {

    const indicesStr: string | undefined = anomaly?.anomalies?.anomaly_indices;
    if (!indicesStr) return {};

    // Regex patterns to capture values
    const srcMatch = indicesStr.match(/\bsrc:\s*([^,]+)/i);
    const dstMatch = indicesStr.match(/\bdst:\s*([^,]+)/i);
    const portsMatch = indicesStr.match(/\bports:\s*([0-9]+)\s*->\s*([0-9]+)/i);

    // Extract values if found
    const src_ip = srcMatch?.[1]?.trim();
    const dst_ip = dstMatch?.[1]?.trim();
    const src_port = portsMatch?.[1] ? Number(portsMatch[1]) : undefined;
    const dst_port = portsMatch?.[2] ? Number(portsMatch[2]) : undefined;

    return { src_ip, dst_ip, src_port, dst_port };
  }

  /**
   * @summary Closes any open dropdown when clicking outside.
   * 
   * @param ev MouseEvent from the document click
   */
  @HostListener('document:click', ['$event'])
  onDocClick(ev: MouseEvent) {
    if (this.dropdownOpenIndex !== null) this.dropdownOpenIndex = null;
  }
}
