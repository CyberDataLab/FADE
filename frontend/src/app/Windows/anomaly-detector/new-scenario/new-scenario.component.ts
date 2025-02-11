import { Component, OnInit, Inject, ViewChild, ElementRef } from '@angular/core';
import { PLATFORM_ID } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { ScenarioService } from '../../scenario.service';
import { Scenario } from '../../../DTOs/Scenario';

@Component({
  selector: 'app-new-scenario',
  standalone: true,
  imports: [
    CommonModule
  ],
  templateUrl: './new-scenario.component.html',
  styleUrl: './new-scenario.component.css'
})

export class NewScenarioComponent implements OnInit{
  activeSections: { [key in 'dataSource' | 'dataProcessing' | 'dataModel']: boolean } = {
    dataSource: false,
    dataProcessing: false,
    dataModel: false
  };

  scenario: Scenario | null = null; 

  draggedElements: HTMLElement[] = [];  
  selectedElements: HTMLElement[] = [];  

  droppedElements: HTMLElement[] = [];

  relativePositions: { element: HTMLElement; offsetX: number; offsetY: number }[] = [];

  isSelecting: boolean = false;
  selectionStart = { x: 0, y: 0 };
  selectionEnd = { x: 0, y: 0 };

  selectedElement: HTMLElement | null = null;  

  isConnecting = false;
  connectionStartElement: HTMLElement | null = null;

  connections: { startElement: HTMLElement, endElement: HTMLElement, line: SVGLineElement }[] = [];

  zoomLevel: number = 1; 
  zoomStep: number = 0.02; 
  minZoom: number = 0.3;  
  maxZoom: number = 1.08;   

  nextElementId: number = 0;

  isNewScenario: boolean = true;

  scenarioId: string | null = null;

  constructor(@Inject(PLATFORM_ID) private platformId: Object, private scenarioService: ScenarioService, private route: ActivatedRoute,) {}

  @ViewChild('configContainer', { static: false }) configContainer?: ElementRef;

  ngOnInit() {
    if (isPlatformBrowser(this.platformId)) {
      document.addEventListener('wheel', (e) => {
        e.preventDefault();
      }, { passive: false });

      document.addEventListener('keydown', (event) => this.onKeyDown(event));
      document.addEventListener('click', (event) => this.onDocumentClick(event));

      const zoomInButton = document.getElementById('zoomIn');
      const zoomOutButton = document.getElementById('zoomOut');
      const saveScenario = document.getElementById('saveScenario');

      if (zoomInButton) {
        zoomInButton.addEventListener('click', () => this.zoomIn());
      }

      if (zoomOutButton) {
        zoomOutButton.addEventListener('click', () => this.zoomOut());
      }

      if (saveScenario) {
        saveScenario.addEventListener('click', () => this.saveScenario());
      }

      this.scenarioService.saveRequested$.subscribe(() => this.saveScenario());
      
      this.scenarioService.setUnsavedChanges(this.droppedElements.length > 0);

      this.scenarioId = this.route.snapshot.paramMap.get('id');

      if (this.scenarioId) {
        this.isNewScenario = false;
        this.loadEditScenario(this.scenarioId);
      } 
    }
  }

  updateUnsavedState() {
    this.scenarioService.setUnsavedChanges(this.droppedElements.length > 0);
  }

  toggleSection(section: 'dataSource' | 'dataProcessing' | 'dataModel') {
    this.activeSections[section] = !this.activeSections[section];
  }

  addDragEventListeners() {
    const draggableElements = document.querySelectorAll('.option');
  
    draggableElements.forEach((element: Element) => {
      const htmlElement = element as HTMLElement;
  
      htmlElement.addEventListener('dragstart', (event) => this.onDragStart(event, false));
      htmlElement.addEventListener('dragend', (event) => this.onDragEnd(event));
    });
  }

  onElementClick(event: MouseEvent, element: EventTarget | null): void {
    if (element instanceof HTMLElement && (element.classList.contains('gear-icon') || element.classList.contains('arrow-icon'))) {
      event.stopPropagation(); 
      return;
    }
  
    if (this.isConnecting && this.connectionStartElement) {
      if (element instanceof HTMLElement) {
        this.createConnection(this.connectionStartElement, element);
  
        this.isConnecting = false;
        this.connectionStartElement = null;
      }
      return;
    }
  
    event.stopPropagation(); 
  
    if (element instanceof HTMLElement) {
      const isCtrlOrCmdPressed = event.ctrlKey || event.metaKey;
  
      if (isCtrlOrCmdPressed) {
        if (this.selectedElements.includes(element)) {
          this.deselectElement(element);
        } else {
          this.selectElement(element);
        }
      } else {
        this.clearSelection();
        this.selectElement(element);
      }
    }
  }

  selectElement(element: HTMLElement) {
    if (!this.selectedElements.includes(element)) {
      this.selectedElements.push(element);
      element.classList.add('selected');
    }
  }
  
  
  deselectElement(element: HTMLElement) {
    this.selectedElements = this.selectedElements.filter((el) => el !== element);
    element.classList.remove('selected');
  }
  
  clearSelection() {
    this.selectedElements.forEach((el) => el.classList.remove('selected'));
    this.selectedElements = [];
  }

  onDocumentClick(event: MouseEvent) {
    if (!this.selectedElements.some((element) => element.contains(event.target as Node))) {
      this.clearSelection(); 
    }
  
    const menu = document.getElementById('context-menu');
    if (menu && !menu.contains(event.target as Node)) {
      this.hideContextMenu();
    }
  }
  
  onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Backspace' || event.key === 'Delete') {
      this.deleteSelectedElements();
    }
  }
  
  deleteSelectedElements(): void {
    if (this.selectedElements.length > 0) {
        const elementsToDelete = [...this.selectedElements];

        this.connections = this.connections.filter((connection) => {
            const isConnected = elementsToDelete.includes(connection.startElement) || 
                              elementsToDelete.includes(connection.endElement);
            
            if (isConnected && connection.line.parentElement) {
                connection.line.parentElement.removeChild(connection.line);
            }
            return !isConnected;
        });

        elementsToDelete.forEach(element => {
            if (element.parentElement) {
                element.parentElement.removeChild(element);
            }
        });

        this.droppedElements = this.droppedElements.filter(el => !elementsToDelete.includes(el));
        
        this.selectedElements = [];
        
        this.updateUnsavedState();
    }
  }

  onDragStart(event: DragEvent, isWorkspace: boolean): void {
    const target = event.target as HTMLElement;
    if (target) {
      if (!isWorkspace) {
        const clone = target.cloneNode(true) as HTMLElement;
        clone.addEventListener('dragstart', (e) => this.onDragStart(e, true));
        clone.addEventListener('dragend', (e) => this.onDragEnd(e));
        this.draggedElements = [clone];
      } else {
        this.draggedElements = this.selectedElements.length > 0 ? [...this.selectedElements] : [target];
      }
  
      this.relativePositions = this.draggedElements.map((element) => {
        const rect = element.getBoundingClientRect();
        return { element, offsetX: 0, offsetY: 0 };
      });
  
      if (event.dataTransfer) {
        event.dataTransfer.setData('text/plain', '');
        event.dataTransfer.setDragImage(target, 0, 0);
      }
  
      if (this.selectedElements.length > 1) {
        const firstElement = this.selectedElements[0];
        const firstRect = firstElement.getBoundingClientRect();
  
        this.relativePositions = this.selectedElements.map((element) => {
          const rect = element.getBoundingClientRect();
          return { 
            element, 
            offsetX: rect.left - firstRect.left, 
            offsetY: rect.top - firstRect.top 
          };
        });
      }
    }
  }

  onDragEnd(event: DragEvent) {
    this.draggedElements = []; 
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
  
    const dropArea = document.getElementById('drop-area');
    if (dropArea) {
      const rect = dropArea.getBoundingClientRect();
      const dropX = (event.clientX - rect.left) / this.zoomLevel;  
      const dropY = (event.clientY - rect.top) / this.zoomLevel;  
  
      this.relativePositions.forEach(({ element, offsetX, offsetY }) => {
        if (!dropArea.contains(element)) {
          element.id = `element-${this.nextElementId++}`;
          element.addEventListener('click', (e) => this.onElementClick(e, element));
          element.addEventListener('contextmenu', (e) => this.onElementClickWorkspace(e, element));
  
          const gearIcon = document.createElement('i');
          gearIcon.className = 'fa fa-cog gear-icon'; 
          gearIcon.style.display = 'none';  
  
          const arrowIcon = document.createElement('i');
          arrowIcon.className = 'fa fa-arrow-right arrow-icon';
          arrowIcon.style.display = 'none'; 
  
          element.addEventListener('mouseenter', () => {
            gearIcon.style.display = 'block';
            arrowIcon.style.display = 'block';
          });
  
          element.addEventListener('mouseleave', () => {
            gearIcon.style.display = 'none';
            arrowIcon.style.display = 'none';
          });
  
          gearIcon.addEventListener('click', (e) => {
            e.stopPropagation(); 
            this.onConfigurationClick(element);  
          });
  
          arrowIcon.addEventListener('click', (e) => {
            e.stopPropagation();
            this.onConnectionClick(element); 
          });
  
          element.appendChild(gearIcon);
          element.appendChild(arrowIcon);
          dropArea.appendChild(element);
        }
  
        element.style.position = 'absolute';
  
        const maxX = dropArea.offsetWidth / this.zoomLevel - element.offsetWidth;
        let newX = dropX + offsetX;
        newX = Math.max(0, Math.min(newX, maxX));
  
        const maxY = dropArea.offsetHeight / this.zoomLevel - element.offsetHeight;
        let newY = dropY + offsetY;
        newY = Math.max(0, Math.min(newY, maxY));
  
        element.style.left = `${newX * this.zoomLevel}px`;  
        element.style.top = `${newY * this.zoomLevel}px`;
  
        this.updateConnections(element);
        this.droppedElements.push(element);
        this.updateUnsavedState();
      });
  
      this.draggedElements = [];
    }
  }
  
  moveElementsToWorkspace(elements: HTMLElement[], x: number, y: number) {
    elements.forEach(element => {
      element.style.position = 'absolute';
      element.style.left = `${x}px`;
      element.style.top = `${y}px`;

      if (!document.getElementById('drop-area')?.contains(element)) {
        document.getElementById('drop-area')?.appendChild(element);
      }
    });
  }

  onMouseMove(event: MouseEvent) {
    const dropArea = document.getElementById('drop-area');
    if (!dropArea) return;
  
    const rect = dropArea.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
  
    this.draggedElements = [];
  
    const elements = Array.from(dropArea.querySelectorAll('.option'));
    elements.forEach((element) => {
      const elRect = element.getBoundingClientRect();
      const elLeft = elRect.left - rect.left;
      const elTop = elRect.top - rect.top;
      const elRight = elLeft + elRect.width;
      const elBottom = elTop + elRect.height;
  
      if (mouseX >= elLeft && mouseX <= elRight && mouseY >= elTop && mouseY <= elBottom) {
        this.selectElement(element as HTMLElement);
      }
    });
  }

  onMouseDown(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (target.closest('.option') || target.closest('.workspace-element')) {
      return;
    }
  
    this.isSelecting = true;
    const dropArea = document.getElementById('drop-area');
    if (dropArea) {
      const rect = dropArea.getBoundingClientRect();
      this.selectionStart = {
        x: (event.clientX - rect.left) / this.zoomLevel,
        y: (event.clientY - rect.top) / this.zoomLevel,
      };
    }
  
    this.clearSelection();  
  
    const selectionBox = document.getElementById('selection-box');
    if (selectionBox) {
      selectionBox.style.left = `${this.selectionStart.x * this.zoomLevel}px`;
      selectionBox.style.top = `${this.selectionStart.y * this.zoomLevel}px`;
      selectionBox.style.width = '0px';
      selectionBox.style.height = '0px';
      selectionBox.style.display = 'block';
    }
  }
  
  
  onMouseMoveSelection(event: MouseEvent) {
    if (!this.isSelecting) return;
  
    const dropArea = document.getElementById('drop-area');
    if (!dropArea) return;
  
    const rect = dropArea.getBoundingClientRect();
    this.selectionEnd = {
      x: (event.clientX - rect.left) / this.zoomLevel,
      y: (event.clientY - rect.top) / this.zoomLevel,
    };
  
    const selectionBox = document.getElementById('selection-box');
    if (selectionBox) {
      const x = Math.min(this.selectionStart.x, this.selectionEnd.x);
      const y = Math.min(this.selectionStart.y, this.selectionEnd.y);
      const width = Math.abs(this.selectionEnd.x - this.selectionStart.x);
      const height = Math.abs(this.selectionEnd.y - this.selectionStart.y);
  
      selectionBox.style.left = `${x * this.zoomLevel}px`;
      selectionBox.style.top = `${y * this.zoomLevel}px`;
      selectionBox.style.width = `${width * this.zoomLevel}px`;
      selectionBox.style.height = `${height * this.zoomLevel}px`;
  
      this.droppedElements.forEach((el) => {
        const elRect = el.getBoundingClientRect();
        const elementLeft = (elRect.left - rect.left) / this.zoomLevel;
        const elementTop = (elRect.top - rect.top) / this.zoomLevel;
        const elementRight = elementLeft + elRect.width / this.zoomLevel;
        const elementBottom = elementTop + elRect.height / this.zoomLevel;
  
        const overlaps =
          elementLeft >= x &&
          elementTop >= y &&
          elementRight <= x + width &&
          elementBottom <= y + height;
  
        if (overlaps) {
          if (!this.selectedElements.includes(el)) {
            this.selectElement(el);
          }
        } else {
          if (this.selectedElements.includes(el)) {
            this.deselectElement(el);
          }
        }
      });
    }
  }
  
  onMouseUp(event: MouseEvent) {
    if (!this.isSelecting) return;
  
    this.isSelecting = false;
  
    this.selectedElements.forEach((el) => {
      el.classList.add('selected');
    });
  
    const selectionBox = document.getElementById('selection-box');
    if (selectionBox) {
      selectionBox.style.display = 'none';
    }
  }
  

  onElementClickWorkspace(event: MouseEvent, element: HTMLElement): void {
    event.preventDefault(); 
    const menu = document.getElementById('context-menu');
    if (menu) {
      const x = event.clientX;
      const y = event.clientY;
  
      menu.style.left = `${x}px`;
      menu.style.top = `${y}px`;
      menu.style.display = 'block';  
      this.selectedElement = element;
    }
  }
  
  onConnectionClick(selectedElement: HTMLElement): void {
    if (selectedElement) {
      this.isConnecting = true;
      this.connectionStartElement = selectedElement;
      this.hideContextMenu();
    }
  }

  createConnection(startElement: HTMLElement, endElement: HTMLElement): void {
    const dropArea = document.getElementById('drop-area');
    if (!dropArea) return;

    if (startElement === endElement) return;

    const svgNamespace = 'http://www.w3.org/2000/svg';
    const svg = dropArea.querySelector('svg') || document.createElementNS(svgNamespace, 'svg');

    if (!dropArea.contains(svg)) {
        svg.setAttribute('width', `${dropArea.offsetWidth}`);
        svg.setAttribute('height', `${dropArea.offsetHeight}`);
        svg.style.position = 'absolute';
        svg.style.top = '0';
        svg.style.left = '0';
        svg.style.pointerEvents = 'none'; 
        dropArea.appendChild(svg);
    }

    const scale = this.getZoomScale();

    const startRect = startElement.getBoundingClientRect();
    const endRect = endElement.getBoundingClientRect();
    const dropAreaRect = dropArea.getBoundingClientRect();

    const distances = this.calculateAllDistances(startRect, endRect);

    const closestPair = this.getClosestPair(distances);

    if (closestPair.startEdge && closestPair.endEdge) {
        let startX = (closestPair.startEdge.x - dropAreaRect.left) / scale;
        let startY = (closestPair.startEdge.y - dropAreaRect.top) / scale;
        let endX = (closestPair.endEdge.x - dropAreaRect.left) / scale;
        let endY = (closestPair.endEdge.y - dropAreaRect.top) / scale;

        const startElementStyles = window.getComputedStyle(startElement);
        const endElementStyles = window.getComputedStyle(endElement);

        const startAdjustmentX = parseInt(startElementStyles.borderLeftWidth, 10) || 0;
        const startAdjustmentY = parseInt(startElementStyles.borderTopWidth, 10) || 0;
        const endAdjustmentX = parseInt(endElementStyles.borderLeftWidth, 10) || 0;
        const endAdjustmentY = parseInt(endElementStyles.borderTopWidth, 10) || 0;

        startX += startAdjustmentX / scale;
        startY += startAdjustmentY / scale;
        endX += endAdjustmentX / scale;
        endY += endAdjustmentY / scale;

        const line = document.createElementNS(svgNamespace, 'line');
        line.setAttribute('x1', `${startX}`);
        line.setAttribute('y1', `${startY}`);
        line.setAttribute('x2', `${endX}`);
        line.setAttribute('y2', `${endY}`);
        line.setAttribute('stroke', 'black');
        line.setAttribute('stroke-width', '2');

        svg.appendChild(line);

        this.connections.push({
            startElement,
            endElement,
            line
        });
    }

    this.isConnecting = false;
    this.connectionStartElement = null;
  }

  private calculateAllDistances(startRect: DOMRect, endRect: DOMRect): { startEdge: { x: number, y: number }, endEdge: { x: number, y: number }, distance: number }[] {
      const startEdges = this.getEdges(startRect);
      const endEdges = this.getEdges(endRect);

      const distances: { startEdge: { x: number, y: number }, endEdge: { x: number, y: number }, distance: number }[] = [];
      
      startEdges.forEach((startEdge) => {
          endEdges.forEach((endEdge) => {
              const distance = Math.hypot(startEdge.x - endEdge.x, startEdge.y - endEdge.y);
              distances.push({ startEdge, endEdge, distance });
          });
      });

      return distances;
  }

  private getEdges(rect: DOMRect): { x: number, y: number }[] {
      const left = { x: rect.left, y: rect.top + rect.height / 2 };     
      const right = { x: rect.right, y: rect.top + rect.height / 2 };  
      const top = { x: rect.left + rect.width / 2, y: rect.top };        
      const bottom = { x: rect.left + rect.width / 2, y: rect.bottom };  

      return [top, bottom, left, right];
  }

  private getClosestPair(distances: { startEdge: { x: number, y: number }, endEdge: { x: number, y: number }, distance: number }[]): { startEdge: { x: number, y: number }, endEdge: { x: number, y: number } } {
      let minDistance = Infinity;
      let closestPair: { startEdge: { x: number, y: number }, endEdge: { x: number, y: number } } = { startEdge: { x: 0, y: 0 }, endEdge: { x: 0, y: 0 } };

      distances.forEach((pair) => {
          if (pair.distance < minDistance) {
              minDistance = pair.distance;
              closestPair = pair;
          }
      });

      return closestPair;
  }

  updateConnections(element: HTMLElement) {
    this.connections.forEach((connection) => {
        if (connection.startElement === element || connection.endElement === element) {
            const dropArea = document.getElementById('drop-area');
            if (!dropArea) return;

            const scale = this.getZoomScale();

            const startRect = connection.startElement.getBoundingClientRect();
            const endRect = connection.endElement.getBoundingClientRect();
            const dropAreaRect = dropArea.getBoundingClientRect();

            const distances = this.calculateAllDistances(startRect, endRect);

            const closestPair = this.getClosestPair(distances);

            if (closestPair.startEdge && closestPair.endEdge) {
                let startX = (closestPair.startEdge.x - dropAreaRect.left) / scale;
                let startY = (closestPair.startEdge.y - dropAreaRect.top) / scale;
                let endX = (closestPair.endEdge.x - dropAreaRect.left) / scale;
                let endY = (closestPair.endEdge.y - dropAreaRect.top) / scale;

                const startElementStyles = window.getComputedStyle(connection.startElement);
                const endElementStyles = window.getComputedStyle(connection.endElement);

                const startAdjustmentX = (parseInt(startElementStyles.borderLeftWidth, 10) || 0) / scale;
                const startAdjustmentY = (parseInt(startElementStyles.borderTopWidth, 10) || 0) / scale;
                const endAdjustmentX = (parseInt(endElementStyles.borderLeftWidth, 10) || 0) / scale;
                const endAdjustmentY = (parseInt(endElementStyles.borderTopWidth, 10) || 0) / scale;

                startX += startAdjustmentX;
                startY += startAdjustmentY;
                endX += endAdjustmentX;
                endY += endAdjustmentY;

                const line = connection.line;
                line.setAttribute('x1', `${startX}`);
                line.setAttribute('y1', `${startY}`);
                line.setAttribute('x2', `${endX}`);
                line.setAttribute('y2', `${endY}`);
            }
        }
    });
  }

  onConfigurationClick(selectedElement: HTMLElement): void {
    if (selectedElement) {
      if (this.configContainer) {
        this.configContainer.nativeElement.classList.add('show');
        
        const configContent = this.configContainer.nativeElement.querySelector('.config-content');
        if (configContent) {
          switch (selectedElement.innerText.trim()) {
            case 'CSV':
              configContent.innerHTML = `
                <h3>CSV file configuration</h3>
                <p>Please select a CSV file:</p>
                <input type="file" id="csv-upload" accept=".csv" (change)="onCSVFileSelected($event)">
              `;
            break;
            case 'Network':
              configContent.innerHTML = `
                <h3>Network file configuration</h3>
                <p>Please select a network file:</p>
                <input type="file" id="network-upload" accept=".txt" (change)="onNetworkFileSelected($event)">
              `;
            break;
            case 'Standard Scaler':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">Standard Scaler Configuration</h3>
                  <label style="display: block; margin-bottom: 60px;">
                      Mean: 
                      <select id="standard-with-mean">
                          <option value="true">Yes</option>
                          <option value="false">No</option>
                      </select>
                  </label>
                  <label style="display: block; margin-bottom: 60px;">
                      Standard Deviation: 
                      <select id="standard-with-std">
                          <option value="true">Yes</option>
                          <option value="false">No</option>
                      </select>
                  </label>
              `;
              break;
            case 'MinMax Scaler':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">MinMax Scaler Configuration</h3>
                  <label style="display: block; margin-bottom: 60px;">
                      Min Value: <input type="number" id="minmax-min" placeholder="Min Value" value="0">
                  </label>
                  <label style="display: block; margin-bottom: 60px;">
                      Max Value: <input type="number" id="minmax-max" placeholder="Max Value" value="1">
                  </label>
                  <label style="display: block; margin-bottom: 60px;">
                      Clip Data: 
                      <select id="minmax-clip">
                          <option value="true">False</option>
                          <option value="false">True</option>
                      </select>
                  </label>
              `;
              break;
            case 'One-Hot Encoding':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">One-Hot Encoding Configuration</h3>
                  <label style="display: block; margin-bottom: 60px;">
                      Handle Unknown Categories: 
                      <select id="onehot-handle">
                          <option value="ignore">Ignore</option>
                          <option value="error">Error</option>
                      </select>
                  </label>
                  <label style="display: block; margin-bottom: 60px;">
                      Drop First Category: 
                      <select id="onehot-drop">
                          <option value="first">First</option>
                          <option value="if_binary">If Binary</option>
                          <option value="none">None</option>
                      </select>
                  </label>
              `;
              break;
            case 'PCA':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">PCA Configuration</h3>
                  <label style="display: block; margin-bottom: 60px;">
                      Number of Components: 
                      <input type="number" id="pca-components" placeholder="Number of Components" value="2">
                  </label>
                  <label style="display: block; margin-bottom: 60px;">
                      Whiten: 
                      <select id="pca-whiten">
                          <option value="true">False</option>
                          <option value="false">True</option>
                      </select>
                  </label>
              `;
              break;
            case 'Normalizer':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">Normalizer Configuration</h3>
                  <label style="display: block; margin-bottom: 60px;">
                      Norm Type:
                      <select id="normalizer-norm">
                          <option value="l2">L2</option>
                          <option value="l1">L1</option>
                          <option value="max">Max</option>
                      </select>
                  </label>
              `;
              break;
            case 'KNN Imputer':
              configContent.innerHTML = '<h3>KNN Imputer Configuration</h3><p>Configuration details for KNN Imputer.</p>';
              break; 
            case 'CNN':
              configContent.innerHTML = '<h3>CNN Configuration</h3><p>Configuration details for CNN.</p>';
              break;
            case 'RNN':
              configContent.innerHTML = '<h3>RNN Configuration</h3><p>Configuration details for RNN.</p>';
              break;
            case 'KNN':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">KNN Configuration</h3>
                  <label style="display: block; margin-bottom: 60px;">
                      Number of Neighbors: <input type="number" id="knn-neighbors" placeholder="Number of neighbors" value="5">
                  </label>
                  <label style="display: block; margin-bottom: 60px;">
                      Weight Function: 
                      <select id="knn-weight">
                          <option value="uniform">Uniform</option>
                          <option value="distance">Distance</option>
                      </select>
                  </label>
                  <label style="display: block; margin-bottom: 60px;">
                      Distance Metric:
                      <select id="knn-metric">
                          <option value="euclidean">Euclidean</option>
                          <option value="manhattan">Manhattan</option>
                          <option value="minkowski">Minkowski</option>
                          <option value="chebyshev">Chebyshev</option>
                          <option value="cosine">Cosine</option>
                      </select>
                  </label>
              `;
              break;
            case 'Random Forest':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">Random Forest Configuration</h3>
                  
                  <label style="display: block; margin-bottom: 60px;">Number of Trees: 
                      <input type="number" id="rf-trees" value="100" min="1" placeholder="Number of trees">
                  </label>
                  
                  <label style="display: block; margin-bottom: 60px;">Max Depth: 
                      <input type="number" id="rf-depth" placeholder="Max depth" min="1">
                      <input type="checkbox" id="rf-depth-none" checked> None
                  </label>
            
                  <label style="display: block; margin-bottom: 60px;">Random State: 
                      <input type="number" id="rf-random-state" placeholder="Random state">
                  </label>
            
                  <label style="display: block; margin-bottom: 60px;">Max Features: 
                      <select id="rf-max-features">
                          <option value="auto">Auto</option>
                          <option value="sqrt">Sqrt</option>
                          <option value="log2">Log2</option>
                          <option value="number">Number</option>
                      </select>
                      <input type="number" id="rf-max-features-number" placeholder="Enter number" style="display: none; margin-top: 10px;">
                  </label>
            
                  <script>
                      document.getElementById('rf-max-features').addEventListener('change', function() {
                          let maxFeaturesInput = document.getElementById('rf-max-features-number');
                          if (this.value === 'number') {
                              maxFeaturesInput.style.display = 'inline-block'; 
                          } else {
                              maxFeaturesInput.style.display = 'none'; 
                          }
                      });
            
                      window.addEventListener('load', function() {
                          let selectElement = document.getElementById('rf-max-features');
                          let numberInput = document.getElementById('rf-max-features-number');
                          if (selectElement.value === 'number') {
                              numberInput.style.display = 'inline-block';
                          } else {
                              numberInput.style.display = 'none'; 
                          }
                      });
                  </script>
              `;
              break;
            case 'Logistic Regression':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">Logistic Regression Configuration</h3>
                  <label style="display: block; margin-bottom: 60px;">Regularization: 
                      <input type="number" step="0.1" id="logreg-c" value="1.0" placeholder="Regularization">
                  </label>
                  <br>
                  <label style="display: block; margin-bottom: 60px;">Penalty: 
                      <select id="logreg-penalty">
                          <option value="l2">L2 (Ridge)</option>
                          <option value="l1">L1 (Lasso)</option>
                          <option value="elasticnet">ElasticNet</option>
                      </select>
                  </label>
                  <br>
                  <label style="display: block; margin-bottom: 60px;">Solver: 
                      <select id="logreg-solver">
                          <option value="lbfgs">lbfgs</option>
                          <option value="liblinear">liblinear</option>
                          <option value="newton-cg">newton-cg</option>
                          <option value="saga">saga</option>
                      </select>
                  </label>
                  <br>
                  <label style="display: block; margin-bottom: 60px;">Maximum Iterations: 
                      <input type="number" step="1" id="logreg-maxiter" value="100" placeholder="Maximun iterations">
                  </label>
              `;
              break;
            case 'SVM':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">SVM Configuration</h3>
                  <label style="display: block; margin-bottom: 60px;">Kernel: 
                      <select id="svm-kernel">
                          <option value="linear">Linear</option>
                          <option value="poly">Polynomial</option>
                          <option value="rbf">RBF</option>
                          <option value="sigmoid">Sigmoid</option>
                      </select>
                  </label>
                  <label style="display: block; margin-bottom: 60px;">Regularization (C): <input type="number" step="0.1" id="svm-c" value="1.0"></label>
                  <label style="display: block; margin-bottom: 60px;">Class Weight: 
                      <select id="svm-class-weight">
                          <option value="balanced">Balanced</option>
                          <option value="none" selected>None</option>
                      </select>
                  </label>
                  <label style="display: block; margin-bottom: 60px;">Gamma: <input type="number" step="0.01" id="svm-gamma" value="0.1" disabled></label>
              
                  <script>
                    const kernelSelect = document.getElementById("svm-kernel");
                    const gammaInput = document.getElementById("svm-gamma");
                
                    kernelSelect.addEventListener('change', function() {
                        const selectedKernel = kernelSelect.value;
                
                        if (selectedKernel === 'rbf' || selectedKernel === 'poly' || selectedKernel === 'sigmoid') {
                            gammaInput.disabled = false;
                        } else {
                            gammaInput.disabled = true;
                        }
                    });
                
                    if (kernelSelect.value === 'rbf' || kernelSelect.value === 'poly' || kernelSelect.value === 'sigmoid') {
                        gammaInput.disabled = false;
                    } else {
                        gammaInput.disabled = true;
                    }
                    </script>
                `;
              break;
            case 'Gradient Boosting':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">Gradient Boosting Configuration</h3>
                  <label style="display: block; margin-bottom: 60px;">Number of Estimators: <input type="number" id="gb-n_estimators" value="100" placeholder="Number of estimators"></label>
                  <label style="display: block; margin-bottom: 60px;">Learning rate: <input type="number" step="0.01" id="gb-learning_rate" value="0.1" placeholder="Learning rate"></label>
                  <label style="display: block; margin-bottom: 60px;">Max Depth: <input type="number" id="gb-max_depth" value="3" placeholder="Max depth"></label>
                  <label style="display: block; margin-bottom: 60px;">Random State: <input type="number" id="gb-random_state" value="42" placeholder="Random state"></label>
              `;
              break;
            case 'Decision Tree':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">Decision Tree Configuration</h3>
                  <label style="display: block; margin-bottom: 60px;">Max Depth: <input type="number" id="dt-depth" value="None"></label>
                  <label style="display: block; margin-bottom: 60px;">Criterion: 
                      <select id="dt-criterion">
                          <option value="gini">Gini</option>
                          <option value="entropy">Entropy</option>
                          <option value="log_loss">Cross-Entropy Loss</option>
                      </select>
                  </label>
                  <label style="display: block; margin-bottom: 60px;">Max Features: 
                      <input type="number" id="dt-max-features" value="None" min="1">
                  </label>
                  <label style="display: block; margin-bottom: 60px;">Splitter: 
                      <select id="dt-splitter">
                          <option value="best">Best</option>
                          <option value="random">Random</option>
                      </select>
                  </label>
                  <label style="display: block; margin-bottom: 60px;">Random State: 
                      <input type="number" id="dt-random-state" value="None">
                  </label>
              `;
              break;
            
            default:
              configContent.innerHTML = '<h3>Configuration</h3><p>Unknown configuration content.</p>';
            break;            
          }
        }
      }
    }
    this.hideContextMenu();  
  }

  onCSVFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input && input.files) {
      const file = input.files[0];
      if (file && file.name.endsWith('.csv')) {
        alert('File upload correctly')
      } else {
        alert('Please, select a CSV file.');
      }
    }
  }

  onNetworkFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input && input.files) {
      const file = input.files[0];
      if (file && file.name.endsWith('.txt')) {
        alert('File upload correctly')
      } else {
        alert('Please, select a txt file.');
      }
    }
  }
  
  closeConfig(): void {
    if (this.configContainer) {
      this.configContainer.nativeElement.classList.remove('show'); 
    }
  }
  
  hideContextMenu(): void {
    const menu = document.getElementById('context-menu');
    if (menu) {
      menu.style.display = 'none';  
    }
  }

  zoomIn() {
    if (this.zoomLevel < this.maxZoom) {
      this.zoomLevel += this.zoomStep;
      this.applyZoom();
    }
  }
  
  zoomOut() {
    if (this.zoomLevel > this.minZoom) {
      this.zoomLevel -= this.zoomStep;
      this.applyZoom();
    }
  }
  
  applyZoom() {
    const dropArea = document.getElementById('drop-area');
    const container = document.querySelector('.workspace');
  
    if (dropArea && container) {
      const dropAreaRect = dropArea.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();
  
      dropArea.style.transformOrigin = 'top left';
      dropArea.style.transform = `scale(${this.zoomLevel})`;
  
      if (dropAreaRect.right > containerRect.right) {
        const excessWidth = dropAreaRect.right - containerRect.right;
        dropArea.style.left = `-${excessWidth}px`;  
      } else {
        dropArea.style.left = '0px';  
      }
  
      if (dropAreaRect.bottom > containerRect.bottom) {
        const excessHeight = dropAreaRect.bottom - containerRect.bottom;
        dropArea.style.top = `-${excessHeight}px`;  
      } else {
        dropArea.style.top = '0px';  
      }
    }
  
    this.selectedElements.forEach((element) => {
      this.updateConnections(element);
    });
  }
  
  private getZoomScale(): number {
    const dropArea = document.getElementById('drop-area');
    if (!dropArea) return 1; 

    const transform = window.getComputedStyle(dropArea).transform;

    if (transform && transform !== 'none') {
        const match = transform.match(/matrix\((.+)\)/);
        if (match) {
            const values = match[1].split(',').map(parseFloat);
            return values[0]; 
        }
    }

    return 1; 
  }

  saveScenario(): void {
    const savedElements = this.droppedElements.map((element: HTMLElement) => ({
      id: element.id,
      type: element.getAttribute('data-type'),
      position: {
        left: element.offsetLeft,
        top: element.offsetTop,
      },
    }));
  
    const savedConnections = this.connections.map(conn => ({
      startId: conn.startElement.id,
      endId: conn.endElement.id,
    }));
  
    const design = {
      elements: savedElements,
      connections: savedConnections,
    };

    if (this.isNewScenario) {
      const name = window.prompt('Please enter the name of the scenario:');
    
      if (name) {
        this.scenarioService.saveScenario(name, design)
          .subscribe({
            next: () => {
              alert('Scenario saved correctly.');
              this.scenarioService.setUnsavedChanges(false);
            },
            error: () => {
              alert('Unexpected error while saving the scenario.');
            }
          });
      } else {
        alert('Error while saving the scenario, you must provide a name.');
      }
    }
    else {
      if (this.scenarioId != null){
        this.scenarioService.editScenario(this.scenarioId, design)
          .subscribe({
            next: () => {
              alert('Scenario actualized correctly.');
              this.scenarioService.setUnsavedChanges(false);
            },
            error: () => {
              alert('Unexpected error while saving the scenario.');
            }
          });
      } 
    } 
  }

  loadEditScenario(uuid: string): void {
    this.scenarioService.getScenarioById(uuid).subscribe(
      (response: Scenario) => {
        this.scenario = response;
        
        const designData = typeof this.scenario.design === 'string' 
          ? JSON.parse(this.scenario.design) 
          : this.scenario.design;
  
        this.loadElementsFromJSON(designData.elements);
        this.loadConnectionsFromJSON(designData.connections || []);
      },
      (error: any) => {
        console.error('Error getting scenario:', error);
      }
    );
  }
  
  triggerFileInput(): void {
    const fileInput = document.getElementById('fileInput') as HTMLInputElement;
    if (fileInput) {
      fileInput.click();
    }
  }

  async loadScenario(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    
    if (this.droppedElements.length > 0) {
      const confirmSave = confirm('Do you want to save the current scenario before loading the new scenario?');
      
      if (confirmSave === null) return; 
      if (confirmSave) {
        await this.saveScenario();
      }
    }

    this.clearCurrentDesign();

    if (input?.files?.length) {
      const file = input.files[0];
      const reader = new FileReader();

      reader.onload = (e: ProgressEvent<FileReader>) => {
        try {
          const data = JSON.parse(e.target?.result as string);
          this.loadElementsFromJSON(data.elements);
          this.loadConnectionsFromJSON(data.connections || []);
        } catch (err) {
          alert('Error loading the scenario. Invalid format.');
        }
      };

      reader.readAsText(file);
    }
    
    input.value = '';
  }

  private clearCurrentDesign(): void {
    const container = document.getElementById('content-container');
    
    if (container) {
      while (container.firstChild) {
        container.removeChild(container.firstChild);
      }
  
      const svgElements = container.getElementsByTagName('svg');
      while (svgElements.length > 0) {
        svgElements[0].parentNode?.removeChild(svgElements[0]);
      }
    }
  
    this.droppedElements.forEach(element => {
      if (element.parentElement) {
        element.parentElement.removeChild(element);
      }
    });
  
    this.droppedElements = [];
    this.selectedElements = [];
  
    this.connections.forEach(connection => {
      if (connection.line.parentElement) {
        connection.line.parentElement.removeChild(connection.line);
      }
    });
    this.connections = [];
  
    setTimeout(() => {
      if (container) {
        void container.offsetHeight;
        
        container.style.display = 'none';
        container.style.display = 'block';
      }
    }, 0);

    this.updateUnsavedState();
  }

  private loadElementsFromJSON(savedElements: any[]): void {
    let maxId = -1;
    savedElements.forEach((element: any) => {
      const newElement = this.createElement(element.type);
      newElement.id = element.id; 
      
      const match = element.id.match(/element-(\d+)/);
      if (match) {
        const idNum = parseInt(match[1], 10);
        if (idNum > maxId) maxId = idNum;
      }
      
      newElement.style.position = 'absolute';
      newElement.style.left = `${element.position.left}px`;
      newElement.style.top = `${element.position.top}px`;

      this.setupElementEvents(newElement);
      this.addControlIcons(newElement);

      document.getElementById('content-container')?.appendChild(newElement);
      this.droppedElements.push(newElement);

    });

    if (maxId !== -1) this.nextElementId = maxId + 1;

    this.updateUnsavedState();
  }

  private loadConnectionsFromJSON(savedConnections: any[]): void {
    savedConnections.forEach(connection => {
      const startElement = document.getElementById(connection.startId);
      const endElement = document.getElementById(connection.endId);
      if (startElement && endElement) {
        this.createConnection(startElement as HTMLElement, endElement as HTMLElement);
      }
    });
  }

  private setupElementEvents(element: HTMLElement): void {
    element.addEventListener('click', (e) => this.onElementClick(e, element));
    element.addEventListener('dragstart', (e) => this.onDragStart(e, true));
    element.addEventListener('contextmenu', (e) => this.onElementClickWorkspace(e, element));
  }

  private addControlIcons(element: HTMLElement): void {
    const gearIcon = document.createElement('i');
    gearIcon.className = 'fa fa-cog gear-icon';
    gearIcon.style.display = 'none';

    const arrowIcon = document.createElement('i');
    arrowIcon.className = 'fa fa-arrow-right arrow-icon';
    arrowIcon.style.display = 'none';

    element.appendChild(gearIcon);
    element.appendChild(arrowIcon);

    element.addEventListener('mouseenter', () => {
      gearIcon.style.display = 'block';
      arrowIcon.style.display = 'block';
    });

    element.addEventListener('mouseleave', () => {
      gearIcon.style.display = 'none';
      arrowIcon.style.display = 'none';
    });

    gearIcon.addEventListener('click', (e) => {
      e.stopPropagation();
      this.onConfigurationClick(element);
    });

    arrowIcon.addEventListener('click', (e) => {
      e.stopPropagation();
      this.onConnectionClick(element);
    });
  }

  private createElement(type: string): HTMLElement {
    const newElement = document.createElement('div');
    newElement.className = 'option';
    newElement.setAttribute('draggable', 'true');
    newElement.setAttribute('data-type', type); 
  
    const icon = document.createElement('i');
    icon.className = this.getIconClass(type);
  
    const label = document.createElement('span');
    label.textContent = this.getLabelText(type);
  
    newElement.appendChild(icon);
    newElement.appendChild(label);
  
    return newElement;
  }
  
  private getIconClass(type: string): string {
    switch (type) {
      case 'CSV': return 'fa fa-file-csv';
      case 'Network': return 'fa fa-network-wired';
      case 'StandardScaler': return 'fa fa-sliders-h';
      case 'MinMaxScaler': return 'fa fa-random';
      case 'OneHotEncoding': return 'fa fa-random';
      case 'PCA': return 'fa fa-cogs'; 
      case 'Normalizer': return 'fa fa-adjust'; 
      case 'KNNImputer': return 'fa fa-users'; 
      case 'CNN': return 'fa fa-brain';
      case 'RNN': return 'fa fa-sync-alt';
      case 'KNN': return 'fa fa-users';
      case 'RandomForest': return 'fa fa-tree';
      case 'LogisticRegression': return 'fa fa-chart-line';
      case 'SVM': return 'fa fa-vector-square';
      case 'GradientBoosting': return 'fa fa-fire';
      case 'DecisionTree': return 'fa fa-tree';
      default: return 'fa fa-question';
    }
  }

  private getLabelText(type: string): string {
    switch (type) {
      case 'StandardScaler': return 'Standard Scaler';
      case 'MinMaxScaler': return 'MinMax Scaler';
      case 'OneHotEncoding': return 'One-Hot Encoding';
      case 'Normalizer': return 'Normalizer';
      case 'KNNImputer': return 'KNN Imputer';
      case 'RandomForest': return 'Random Forest';
      case 'LogisticRegression': return 'Logistic Regression';
      case 'GradientBoosting': return 'Gradient Boosting';
      case 'DecisionTree': return 'Decision Tree';
      default: return type;
    }
  }

}
