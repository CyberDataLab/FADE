import { Component, OnInit, Inject, ViewChild, ElementRef } from '@angular/core';
import { PLATFORM_ID, Renderer2 } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { ScenarioService } from '../../scenario.service';
import { Scenario } from '../../../DTOs/Scenario';
import { HttpClient } from '@angular/common/http';

@Component({
    selector: 'app-new-scenario',
    imports: [
        CommonModule
    ],
    templateUrl: './new-scenario.component.html',
    styleUrl: './new-scenario.component.css'
})

export class NewScenarioComponent implements OnInit{
  config: any = {};

  activeSections: { [key: string]: boolean } = {};

  activeSubSections: { [key in 'classification' | 'regression' | 'anomalyDetection' | 'monitoring']: boolean } = {
    classification: false,
    regression: false,
    anomalyDetection: false,
    monitoring: false
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

  lastDesign: string | null = null;

  actualDesign: string | null = null;

  selectedCSVFile: File | null = null;

  private elementParameters: { [elementId: string]: any } = {};
  private currentCSVElementId: string | null = null;

  constructor(@Inject(PLATFORM_ID) private platformId: Object, private scenarioService: ScenarioService, private route: ActivatedRoute, private renderer: Renderer2, private http: HttpClient) {}

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
      this.loadSections();
    }
  }

  loadSections() {
    this.http.get<any>('assets/config.json').subscribe(
      (data:any) => {
        this.config = data;
      },
      (error:any) => {
        console.error('Error cargando el JSON:', error);
      }
    );
  }

  updateUnsavedState() {
    this.scenarioService.setUnsavedChanges(this.droppedElements.length > 0);
  }

  toggleSection(sectionName: string) {
    this.activeSections[sectionName] = !this.activeSections[sectionName];
  }

  toggleSubSection(section: string): void {
    if (section === 'classification' || section === 'regression' || section === 'anomalyDetection' || section === 'monitoring') {
      this.activeSubSections[section] = !this.activeSubSections[section];
    }
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
    if (!dropArea) return;
  
    const rect = dropArea.getBoundingClientRect();
    const scale = this.zoomLevel;
  
    const dropX = (event.clientX - rect.left) / scale;
    const dropY = (event.clientY - rect.top) / scale;
  
    const intendedPositions = this.relativePositions.map(({ element, offsetX, offsetY }) => {
      const maxX = dropArea.offsetWidth / scale - element.offsetWidth;
      let newX = dropX + offsetX;
      newX = Math.max(0, Math.min(newX, maxX));
  
      const maxY = dropArea.offsetHeight / scale - element.offsetHeight;
      let newY = dropY + offsetY;
      newY = Math.max(0, Math.min(newY, maxY));
  
      return { element, newX, newY };
    });
  
    let hasCollision = false;
  
    intendedPositions.forEach(({ element, newX, newY }) => {
      const collidesWithExisting = this.droppedElements.some(existing => 
        !this.draggedElements.includes(existing) && 
        this.isColliding(element, newX, newY, existing)
      );
  
      const collidesWithDragged = intendedPositions.some(other => 
        other.element !== element && 
        this.isColliding(element, newX, newY, other.element, other.newX, other.newY)
      );
  
      if (collidesWithExisting || collidesWithDragged) hasCollision = true;
    });
  
    if (hasCollision) {
      this.draggedElements = [];
      return;
    }
  
    intendedPositions.forEach(({ element, newX, newY }) => {
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
      element.style.left = `${newX * scale}px`;
      element.style.top = `${newY * scale}px`;
  
      this.updateConnections(element);
      if (!this.droppedElements.includes(element)) {
        this.droppedElements.push(element);
      }
    });
  
    this.updateUnsavedState();
    this.draggedElements = [];
  }

  isColliding(
    element1: HTMLElement,
    newX1: number,
    newY1: number,
    element2: HTMLElement,
    newX2?: number,
    newY2?: number
  ): boolean {
    const rect1 = {
      x: newX1,
      y: newY1,
      width: element1.offsetWidth,
      height: element1.offsetHeight
    };
  
    const rect2 = {
      x: newX2 ?? element2.offsetLeft,
      y: newY2 ?? element2.offsetTop,
      width: element2.offsetWidth,
      height: element2.offsetHeight
    };
  
    return !(
      rect1.x + rect1.width < rect2.x ||
      rect1.x > rect2.x + rect2.width ||
      rect1.y + rect1.height < rect2.y ||
      rect1.y > rect2.y + rect2.height
    );
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
        const elementType = selectedElement.getAttribute('data-type');
        
        if (!elementType) return;

        if (elementType === 'CSV') {
          this.handleCSVConfiguration(selectedElement, configContent);
          return;
        } else if (elementType === 'ClassificationMonitor') {
          this.handleClassificationMonitorConfiguration(selectedElement, configContent);
          return;
        } else if (elementType === 'RegressionMonitor') {
          this.handleRegressionMonitorConfiguration(selectedElement, configContent);
          return;
        }

        const elementConfig = this.getElementConfig(elementType);
        if (!elementConfig) return;

        configContent.innerHTML = this.generateConfigHTML(elementConfig, selectedElement.id);
        this.setupDynamicInputs(selectedElement, elementConfig);
      }
    }
    this.hideContextMenu();
  }

  private getElementConfig(elementType: string): any {
    const config = this.config;
    
    const deepSearch = (obj: any): any => {
      if (obj.elements) {
        const found = obj.elements.find((e: any) => e.type === elementType);
        if (found) return found;
      }
      if (obj.classification) {
        const found = obj.classification.find((e: any) => e.type === elementType);
        if (found) return found;
      }
      if (obj.regression) {
        const found = obj.regression.find((e: any) => e.type === elementType);
        if (found) return found;
      }
      if (obj.anomalyDetection) {
        const found = obj.anomalyDetection.find((e: any) => e.type === elementType);
        if (found) return found;
      }

      if (config.properties) {
        return config.properties.find((prop: any) => prop.type === 'csv-columns-array');
      }
      
      return null;
    };
  
    return deepSearch(config.sections.dataSource) ||
           deepSearch(config.sections.dataProcessing) ||
           deepSearch(config.sections.dataModel);
  }
  
  private generateConfigHTML(config: any, elementId: string): string {
    let html = `<h3 style="margin-bottom: 30px;">${config.displayName} Configuration</h3>`;
    
    if (!config.properties || !Array.isArray(config.properties)) {
      console.error(`Configuración inválida para ${config.type}`);
      return html + '<p>Error de configuración</p>';
    }
  
    config.properties.forEach((prop: any) => {
      if (!prop.name || !prop.type) {
        console.warn(`Propiedad inválida en ${config.type}:`, prop);
        return;
      }
      
      html += this.generatePropertyHTML(prop, elementId);
    });
  
    return html;
  }
  
  private generatePropertyHTML(prop: any, elementId: string): string {
    let html = '';
    const currentValue = this.elementParameters[elementId]?.[prop.name] || prop.default;
    const formattedValue = currentValue !== undefined ? currentValue.toString() : prop.default;

    switch (prop.type) {
      case 'conditional-select':
        html += `
          <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
            <label for="${prop.name}-${elementId}" style="flex: 1;">${prop.label}:</label>
            <select id="${prop.name}-select-${elementId}" style="height: 3.6em; padding: 0.75em 1em; font-size: 16px; line-height: 1.2; flex: 2; box-sizing: border-box;">
              ${prop.options.map((opt: string) => `
                <option value="${opt}" ${currentValue === opt ? 'selected' : ''}>
                  ${opt}
                </option>`).join('')}
            </select>
          </div>`;
        break;

      case 'select':
        html += `
          <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
            <label for="${prop.name}-${elementId}" style="flex: 1;">${this.formatPropertyName(prop.label)}:</label>
            <select id="${prop.name}-${elementId}" style="height: 3.6em; padding: 0.75em 1em; font-size: 16px; line-height: 1.2; flex: 2; box-sizing: border-box;">
              ${prop.options.map((opt: string) => `
                <option value="${opt}" ${formattedValue === opt ? 'selected' : ''}>
                  ${this.formatOptionName(opt)}
                </option>`
              ).join('')}
            </select>
          </div>`;
        break;

      case 'number':
        const hasConditional = prop.conditional !== undefined;
        const initialDisplay = hasConditional ? 'none' : 'grid';
        const divId = `${prop.name}-row-${elementId}`;

        html += `
          <div id="${divId}" style="display: ${initialDisplay}; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
            <label for="${prop.name}-${elementId}" style="text-align: left;">${this.formatPropertyName(prop.label)}:</label>
            <input type="number" id="${prop.name}-${elementId}" placeholder="${prop.placeholder}" 
                  value="${currentValue}" 
                  ${prop.min ? `min="${prop.min}"` : ''}
                  ${prop.step ? `step="${prop.step}"` : ''}
                  style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
          </div>`;
        break;
    }

    return html;
  }


  private formatPropertyName(name: string): string {
    return name
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, str => str.toUpperCase())
      .replace(/With/g, 'With ');
  }
  
  private formatOptionName(option: string): string {
    return option === 'True' ? 'True' : 
           option === 'False' ? 'False' : 
           option;
  }
  
  private setupDynamicInputs(element: HTMLElement, config: any): void {
    const elementId = element.id;
    
    if (!this.elementParameters[elementId]) {
      this.elementParameters[elementId] = {};
      
      config.properties.forEach((prop: any) => {
        this.elementParameters[elementId][prop.name] = prop.default;

        if (prop.conditional) {
          const parentValue = this.elementParameters[elementId][prop.conditional.dependsOn];
          if (parentValue !== prop.conditional.value) {
            this.elementParameters[elementId][prop.name] = prop.default;
          }
        }
      });
    }

    config.properties.forEach((prop: any) => {
      const paramKey = prop.name;
      const controlId = `${paramKey}-${elementId}`;
      
      switch (prop.type) {
        case 'conditional-select': {
          const selectId = `${paramKey}-select-${elementId}`;
          const select = document.getElementById(selectId) as HTMLSelectElement;
      
          if (select) {
            if (!(paramKey in this.elementParameters[elementId])) {
                this.elementParameters[elementId][paramKey] = prop.default;
            }
    
            select.value = this.elementParameters[elementId][paramKey];
    
            select.addEventListener('change', () => {
              const newValue = select.value;
              this.elementParameters[elementId][paramKey] = newValue;
  
              config.properties
                .filter((p: any) => p.conditional?.dependsOn === paramKey)
                .forEach((dependentProp: any) => {
                  const dependentRow = document.getElementById(`${dependentProp.name}-row-${elementId}`);

                  if (dependentRow) {
                    const isVisible = newValue === dependentProp.conditional.value;
                    dependentRow.style.display = isVisible ? 'grid' : 'none';

                    if (isVisible) {
                      if (!(dependentProp.name in this.elementParameters[elementId])) {
                        this.elementParameters[elementId][dependentProp.name] = dependentProp.default;
                      }
                    } else {
                      delete this.elementParameters[elementId][dependentProp.name];
                    }
                  }
                });
            });
          }
          break;
        }
      
        case 'number': {
          const input = document.getElementById(controlId) as HTMLInputElement;
          if (input) {
            input.value = this.elementParameters[elementId][paramKey] || '';
    
            input.addEventListener('input', () => {
              const parentProp = config.properties.find((p: any) => p.name === prop.conditional?.dependsOn);
              if (parentProp && this.elementParameters[elementId][parentProp.name] === 'custom') {
                this.elementParameters[elementId][paramKey] = input.value;
              } else {
                delete this.elementParameters[elementId][paramKey];
              }
            });
    
            if (prop.conditional) {
              const parentValue = this.elementParameters[elementId][prop.conditional.dependsOn];
              const row = document.getElementById(`${prop.name}-row-${elementId}`);
              if (row) {
                row.style.display = parentValue === prop.conditional.value ? 'grid' : 'none';
              }
            }
          }
          break;
        }

        case 'select': {
          const selectEl = document.getElementById(controlId) as HTMLSelectElement;
          if (selectEl) {
            selectEl.value = this.elementParameters[elementId][paramKey] || '';

            selectEl.addEventListener('change', () => {
              if (selectEl.value === 'custom') {
                this.elementParameters[elementId][paramKey] = 'custom';
              } else {
                this.elementParameters[elementId][paramKey] = selectEl.value;
                delete this.elementParameters[elementId][`${paramKey}_custom`];
              }
            });
          }
          break;
        }
      }
    });
  }

  private handleCSVConfiguration(selectedElement: HTMLElement, configContent: HTMLElement): void {
    configContent.innerHTML = `<h3>CSV file configuration</h3><p>Please select a CSV file:</p> <div id="csv-columns-selection"></div>`;
    
    const input = this.createFileInput('csv-upload', '.csv', (e) => this.onCSVFileSelected(e));
    const fileNameElement = this.createFileNameElement();
    
    configContent.appendChild(input);
    configContent.appendChild(fileNameElement);
    
    this.currentCSVElementId = selectedElement.id;
    if (this.elementParameters[selectedElement.id]?.columns) {
      this.updateCSVColumnSelectionUI(
        Object.keys(this.elementParameters[selectedElement.id].columns), 
        selectedElement.id
      );
    }
  }
  
  private handleClassificationMonitorConfiguration(selectedElement: HTMLElement, configContent: HTMLElement): void {
    configContent.innerHTML = `<h3>Classification Monitor Configuration</h3><p>Select metrics to monitor:</p><div id="metrics-selection"></div>`;
    const metrics = ['f1Score', 'accuracy', 'recall', 'precision', 'confusionMatrix'];
    this.updateClassificationMetricsSelectionUI(metrics, selectedElement.id);
  }

  private handleRegressionMonitorConfiguration(selectedElement: HTMLElement, configContent: HTMLElement): void {
    configContent.innerHTML = `<h3>Regression Monitor Configuration</h3><p>Select metrics to monitor:</p><div id="metrics-selection"></div>`;
    const metrics = ['mse', 'rmse', 'mae', 'r2', 'msle'];
    this.updateRegressionMetricsSelectionUI(metrics, selectedElement.id);
  }
  
  private createFileInput(id: string, accept: string, handler: (e: Event) => void): HTMLInputElement {
    const input = document.createElement('input');
    input.type = 'file';
    input.id = id;
    input.accept = accept;
    input.addEventListener('change', handler);
    return input;
  }
  
  private createFileNameElement(): HTMLElement {
    const fileNameElement = document.createElement('p');
    fileNameElement.id = 'file-name';
    return fileNameElement;
  }

  onCSVFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input && input.files) {
      const file = input.files[0];
      if (file && file.name.endsWith('.csv')) {
        this.selectedCSVFile = file;
        
        const reader = new FileReader();
        reader.onload = (e: any) => {
          const text = e.target.result;
          const rows = text.split('\n');
          if (rows.length < 1) return;
          
          const columns = rows[0].split(',').map((col: string) => col.trim().replace(/^"|"$/g, ''));
  
          const elementId = this.currentCSVElementId;
          if (!elementId) return;
          
          this.elementParameters[elementId] = {
            csvFileName: file.name,
            columns: columns.map((col:any) => ({
              name: col.trim(),
              selected: true
            }))
          };
          
          this.updateCSVColumnSelectionUI(columns, elementId);
        };
        reader.readAsText(file);
      }
    }
  }

  updateCSVColumnSelectionUI(columns: string[], elementId: string): void {
    const configContent = this.configContainer?.nativeElement.querySelector('.config-content');
    if (!configContent) return;
  
    let columnSelectionDiv = document.getElementById('csv-columns-container');
  
    if (!columnSelectionDiv) {
      columnSelectionDiv = this.renderer.createElement('div');
      this.renderer.setAttribute(columnSelectionDiv, 'id', 'csv-columns-container');
      this.renderer.setAttribute(columnSelectionDiv, 'class', 'csv-columns-container');
    } else {
      columnSelectionDiv.innerHTML = '';
    }
  
    if (!this.elementParameters[elementId]?.columns) {
      this.elementParameters[elementId] = { 
        columns: columns.map(col => ({ name: col.trim(), selected: true })) 
      };
    }
  
    this.elementParameters[elementId].columns.forEach((col: any) => {
      const columnElement = this.renderer.createElement('div');
      this.renderer.setAttribute(columnElement, 'class', 'column-item');

      if (col.selected) {
        this.renderer.addClass(columnElement, 'selected');
      }

      const columnText = this.renderer.createText(col.name);
      this.renderer.appendChild(columnElement, columnText);

      this.renderer.listen(columnElement, 'click', () => {
        col.selected = !col.selected;
        columnElement.classList.toggle('selected');
        
        this.elementParameters[elementId].columns = [...this.elementParameters[elementId].columns];
      });

      this.renderer.appendChild(columnSelectionDiv, columnElement);
    });
  
    this.renderer.appendChild(configContent, columnSelectionDiv);
  }

  updateClassificationMetricsSelectionUI(metrics: string[], elementId: string): void {
    const configContent = this.configContainer?.nativeElement.querySelector('.config-content');
    if (!configContent) return;
  
    let metricsDiv = document.getElementById('metrics-container');
    
    if (!metricsDiv) {
      metricsDiv = this.renderer.createElement('div');
      this.renderer.setAttribute(metricsDiv, 'id', 'metrics-container');
      this.renderer.setAttribute(metricsDiv, 'class', 'metrics-container');
    } else {
      metricsDiv.innerHTML = '';
    }
  
    if (!this.elementParameters[elementId]) {
      this.elementParameters[elementId] = { metrics: {} };
      metrics.forEach(metric => {
        this.elementParameters[elementId].metrics[metric] = true;
      });
    }
  
    const storedMetrics = this.elementParameters[elementId].metrics;
  
    metrics.forEach(metric => {
      const metricElement = this.renderer.createElement('div');
      this.renderer.setAttribute(metricElement, 'class', `metric-item ${storedMetrics[metric] ? 'selected' : ''}`);
      
      const metricText = this.renderer.createText(metric);
      this.renderer.appendChild(metricElement, metricText);
  
      this.renderer.listen(metricElement, 'click', () => {
        storedMetrics[metric] = !storedMetrics[metric];
        metricElement.classList.toggle('selected');
        this.elementParameters[elementId].metrics = { ...storedMetrics };
      });
  
      this.renderer.appendChild(metricsDiv, metricElement);
    });
  
    this.renderer.appendChild(configContent, metricsDiv);
  }

  updateRegressionMetricsSelectionUI(metrics: string[], elementId: string): void {
    const configContent = this.configContainer?.nativeElement.querySelector('.config-content');
    if (!configContent) return;
  
    let metricsDiv = document.getElementById('metrics-container');
    
    if (!metricsDiv) {
      metricsDiv = this.renderer.createElement('div');
      this.renderer.setAttribute(metricsDiv, 'id', 'metrics-container');
      this.renderer.setAttribute(metricsDiv, 'class', 'metrics-container');
    } else {
      metricsDiv.innerHTML = '';
    }
  
    if (!this.elementParameters[elementId]) {
      this.elementParameters[elementId] = { metrics: {} };
      metrics.forEach(metric => {
        this.elementParameters[elementId].metrics[metric] = true;
      });
    }
  
    const storedMetrics = this.elementParameters[elementId].metrics;
  
    metrics.forEach(metric => {
      const metricElement = this.renderer.createElement('div');
      this.renderer.setAttribute(metricElement, 'class', `metric-item ${storedMetrics[metric] ? 'selected' : ''}`);
      
      const metricText = this.renderer.createText(metric);
      this.renderer.appendChild(metricElement, metricText);
  
      this.renderer.listen(metricElement, 'click', () => {
        storedMetrics[metric] = !storedMetrics[metric];
        metricElement.classList.toggle('selected');
        this.elementParameters[elementId].metrics = { ...storedMetrics };
      });
  
      this.renderer.appendChild(metricsDiv, metricElement);
    });
  
    this.renderer.appendChild(configContent, metricsDiv);
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

  saveParameters(selectedElement: HTMLElement, nameElement: string): void {
    const elementId = selectedElement.id;
    if (!this.elementParameters[elementId]) {
      this.elementParameters[elementId] = {};
    }
  
    if (nameElement === 'CSV') {
      this.handleCSVParameters(elementId);
    } else if (nameElement === 'ClassificationMonitor') {
      this.handleClassificationMonitorParameters(elementId);
    } else if (nameElement === 'RegressionMonitor') {
      this.handleRegressionMonitorParameters(elementId);
    }
  }

  private handleCSVParameters(elementId: string): void {
    const csvInput = document.getElementById('csv-upload') as HTMLInputElement;
    if (csvInput?.files?.[0]) {
      this.elementParameters[elementId].csvFileName = csvInput.files[0].name;
    }
  }
  
  private handleClassificationMonitorParameters(elementId: string): void {
    const metricElements = document.querySelectorAll('.metric-item');
    this.elementParameters[elementId].metrics = {};
    
    metricElements.forEach(el => {
      const metricName = el.textContent?.trim();
      if (metricName) {
        this.elementParameters[elementId].metrics[metricName] = el.classList.contains('selected');
      }
    });
  }

  private handleRegressionMonitorParameters(elementId: string): void {
    const metricElements = document.querySelectorAll('.metric-item');
    this.elementParameters[elementId].metrics = {};
    
    metricElements.forEach(el => {
      const metricName = el.textContent?.trim();
      if (metricName) {
        this.elementParameters[elementId].metrics[metricName] = el.classList.contains('selected');
      }
    });
  }

  saveScenario(): void {
    const savedElements = this.droppedElements.map((element: HTMLElement) => {
      const elementParams = this.elementParameters[element.id] || {};
      
      if (element.getAttribute('data-type') === 'CSV' && elementParams.columns) {
        elementParams.columns = elementParams.columns.map((col: any) => ({
          name: col.name,
          selected: col.selected
        }));
      }
  
      return {
        id: element.id,
        type: element.getAttribute('data-type'),
        position: {
          left: element.offsetLeft,
          top: element.offsetTop,
        },
        parameters: elementParams
      };
    });
  
    const savedConnections = this.connections.map(conn => ({
      startId: conn.startElement.id,
      endId: conn.endElement.id,
    }));
  
    const design = {
      elements: savedElements,
      connections: savedConnections,
    };

    this.actualDesign = typeof design;

    if (this.isNewScenario) {
      const name = window.prompt('Please enter the name of the scenario:');
    
      if (name) {
        this.scenarioService.saveScenario(name, design, this.selectedCSVFile || undefined)
          .subscribe({
            next: (response:any) => {
              alert('Scenario saved correctly.');
              this.scenarioId = response.uuid
              this.isNewScenario = false;
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
        this.scenarioService.editScenario(this.scenarioId, design, this.selectedCSVFile || undefined)
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
  
        this.lastDesign = typeof this.scenario.design;
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
      if (element.type === 'CSV' && element.parameters?.columns) {
        this.elementParameters[element.id] = {
          ...element.parameters,
          columns: element.parameters.columns 
        };
      }
      const newElement = this.createElement(element.type);
      newElement.id = element.id; 

      if (element.parameters) {
        this.elementParameters[element.id] = element.parameters;
      }
      
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
      case 'ClassificationMonitor': return 'fas fa-desktop';
      case 'RegressionMonitor': return 'fas fa-desktop';
      case 'CNN': return 'fa fa-brain';
      case 'RNN': return 'fa fa-sync-alt';
      case 'KNN': return 'fa fa-users';
      case 'RandomForest': return 'fa fa-tree';
      case 'LogisticRegression': return 'fa fa-chart-line';
      case 'LinearRegression': return 'fa fa-chart-line';
      case 'SVM': return 'fa fa-vector-square';
      case 'GradientBoosting': return 'fa fa-fire';
      case 'DecisionTree': return 'fa fa-tree';
      case 'IsolationForest': return 'fa fa-tree';
      case 'Autoencoder': return 'fa fa-network-wired';
      case 'OneClassSVM': return 'fa fa-cogs';
      case 'KMeans': return 'fa fa-clone';
      case 'LOF': return 'fa fa-users';
      case 'DBSCAN': return 'fa fa-sitemap';
      case 'GMM': return 'fa fa-cogs';
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
      case 'LinearRegression': return 'Linear Regression';
      case 'GradientBoosting': return 'Gradient Boosting';
      case 'DecisionTree': return 'Decision Tree';
      case 'IsolationForest': return 'Isolation Forest';
      case 'Autoencoder': return 'Auto-encoder';
      case 'OneClassSVM': return 'One-Class SVM';
      case 'KMeans': return 'K-Means';
      case 'ClassificationMonitor': return 'Classification Monitor';
      case 'RegressionMonitor': return 'Regression Monitor';
      default: return type;
    }
  }
}
