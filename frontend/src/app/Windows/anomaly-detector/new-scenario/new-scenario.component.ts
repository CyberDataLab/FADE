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

  lastDesign: string | null = null;

  actualDesign: string | null = null;

  private elementParameters: { [elementId: string]: any } = {};

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
    if (!dropArea) return;
  
    const rect = dropArea.getBoundingClientRect();
    const scale = this.zoomLevel;
  
    const dropX = (event.clientX - rect.left) / scale;
    const dropY = (event.clientY - rect.top) / scale;
  
    // Calcular nuevas posiciones
    const intendedPositions = this.relativePositions.map(({ element, offsetX, offsetY }) => {
      const maxX = dropArea.offsetWidth / scale - element.offsetWidth;
      let newX = dropX + offsetX;
      newX = Math.max(0, Math.min(newX, maxX));
  
      const maxY = dropArea.offsetHeight / scale - element.offsetHeight;
      let newY = dropY + offsetY;
      newY = Math.max(0, Math.min(newY, maxY));
  
      return { element, newX, newY };
    });
  
    // Verificar colisiones
    let hasCollision = false;
  
    intendedPositions.forEach(({ element, newX, newY }) => {
      // Verificar contra elementos existentes
      const collidesWithExisting = this.droppedElements.some(existing => 
        !this.draggedElements.includes(existing) && 
        this.isColliding(element, newX, newY, existing)
      );
  
      // Verificar contra otros elementos arrastrados
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
  
    // Colocar elementos si no hay colisiones
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
        let nameElement = "";
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
                <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                    <label for="standard-with-mean" style="flex: 1;">Mean:</label>
                    <select id="standard-with-mean" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box; margin-top: -10px;">
                        <option value="True">True</option>
                        <option value="False">False</option>
                    </select>
                </div>
                <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                    <label for="standard-with-std" style="flex: 1;">Standard Deviation:</label>
                    <select id="standard-with-std" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box; margin-top: -10px;">
                        <option value="True">True</option>
                        <option value="False">False</option>
                    </select>
                </div>

              `;
              nameElement = "Standard Scaler";
              break;

            case 'MinMax Scaler':
              configContent.innerHTML = `
                <h3 style="margin-bottom: 40px;">MinMax Scaler Configuration</h3>
                <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                  <label style="text-align: left;">Min Value: </label>
                  <input type="number" id="minmax-min" placeholder="Min value" value="0" min="0"
                        style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                </div>
                <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                  <label style="text-align: left;">Max Value: </label>
                  <input type="number" id="minmax-max" placeholder="Max value" value="1" min="1"
                        style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                </div>
                <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                  <label for="minmax-clip" style="flex: 1;">Clip:</label>
                  <select id="minmax-clip" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box; margin-top: -10px;">
                      <option value="False">False</option>
                      <option value="True">True</option>
                  </select>
                </div>
              `;
              nameElement = "MinMax Scaler";
              break;

            case 'One-Hot Encoding':
              configContent.innerHTML = `
                <h3 style="margin-bottom: 40px;">One-Hot Encoding Configuration</h3>
                <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                  <label for="onehot-handle" style="flex: 1; ">Handle Unknown:</label>
                  <select id="onehot-handle" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box; margin-top: -10px;">
                      <option value="error">Error</option>
                      <option value="ignore">Ignore</option>
                      <option value="infrequent_if_exist">Infrequent if exist</option>
                      <option value="warn">Warn</option>
                  </select>
                </div>
                <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                  <label for="onehot-drop" style="flex: 1; ">Drop:</label>
                  <select id="onehot-drop" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box; margin-top: -10px;">
                      <option value="None">None</option>
                      <option value="first">First</option>
                      <option value="if_binary">If binary</option>
                  </select>
                </div>
              `;
              nameElement = "One-Hot Encoding";
              break;

              case 'PCA':
                configContent.innerHTML = `
                    <h3 style="margin-bottom: 40px;">PCA Configuration</h3>
                    
                    <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                        <label for="pca-components-select" style="flex: 1;">Number of components:</label>
                        <select id="pca-components-select" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box; margin-top: -10px;">
                            <option value="None">None</option>
                            <option value="custom">Custom</option>
                        </select>
                    </div>
            
                    <div id="pca-components-container" style="display: none; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                        <label for="pca-components-input" style="text-align: left;">Custom Number of Components: </label>
                        <input type="number" id="pca-components-input" placeholder="Number of components" value="1" min="1"
                               style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                    </div>
            
                    <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                        <label for="pca-whiten" style="flex: 1;">Whiten:</label>
                        <select id="pca-whiten" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box; margin-top: -10px;">
                            <option value="False">False</option>
                            <option value="True">True</option>
                        </select>
                    </div>
                `;

                const scriptPCA = document.createElement('script');
                scriptPCA.innerHTML = `
            
                  // Agregar funcionalidad para mostrar u ocultar el input de número de componentes
                  const pcaSelect = document.getElementById('pca-components-select');
                  const pcaContainer = document.getElementById('pca-components-container');
              
                  function updatePCAComponentsVisibility() {
                      pcaContainer.style.display = (pcaSelect.value === 'custom') ? 'grid' : 'none';
                  }
              
                  pcaSelect.addEventListener('change', updatePCAComponentsVisibility);
                  updatePCAComponentsVisibility(); // Ejecutar al cargar
                `;
                document.body.appendChild(scriptPCA);
                nameElement = "PCA";
                break;
            

            case 'Normalizer':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">Normalizer Configuration</h3>
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                    <label for="normalizer-norm" style="flex: 1; ">Norm:</label>
                    <select id="normalizer-norm" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box;">
                        <option value="l2">L2</option>
                        <option value="l1">L1</option>
                        <option value="max">Max</option>
                    </select>
                  </div>
              `;
              nameElement = "Normalizer";
              break;

            case 'KNN Imputer':
              configContent.innerHTML = `
                <h3 style="margin-bottom: 40px;">KNN Imputer Configuration</h3>
                <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                  <label style="text-align: left;">Number of Neighbors: </label>
                  <input type="number" id="knn-neighbors" placeholder="Number of neighbors" value="5" min="1"
                        style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                </div>
                <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                  <label for="knn-weight" style="flex: 1; ">Weights:</label>
                  <select id="knn-weight" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box;">
                      <option value="uniform">Uniform</option>
                      <option value="distance">Distance</option>
                  </select>
                </div>
              `;
              nameElement = "KNN Imputer";
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
                  <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                    <label style="text-align: left;">Number of Neighbors: </label>
                    <input type="number" id="knn-neighbors" placeholder="Number of neighbors" value="5" min="1"
                          style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                  </div>
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                    <label for="knn-weight" style="flex: 1; ">Weights:</label>
                    <select id="knn-weight" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box;">
                        <option value="uniform">Uniform</option>
                        <option value="distance">Distance</option>
                    </select>
                  </div>
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                    <label for="knn-algorithm" style="flex: 1; ">Algorithm:</label>
                    <select id="knn-algorithm" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box; ">
                        <option value="auto">Auto</option>
                        <option value="ball_tree">BallTree</option>
                        <option value="kd_tree">KDTree</option>
                        <option value="brute">Brute</option>
                    </select>
                  </div>
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                    <label for="knn-metric" style="flex: 1; ">Metric:</label>
                    <select id="knn-metric" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box; ">
                        <option value="minkowski">Minkowski</option>
                        <option value="euclidean">Euclidean</option>
                        <option value="manhattan">Manhattan</option>
                        <option value="chebyshev">Chebyshev</option>
                        <option value="cosine">Cosine</option>
                    </select>
                  </div>
              `;
              nameElement = "KNN";
              break;
            case 'Random Forest':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">Random Forest Configuration</h3>
          
                  <!-- Número de árboles -->
                  <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                      <label style="text-align: left;">Number of Trees: </label>
                      <input type="number" id="rf-trees" placeholder="Number of trees" value="100" min="1"
                              style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                  </div>
          
                  <!-- Max Depth -->
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                      <label for="rf-depth-select" style="flex: 1;">Max Depth:</label>
                      <select id="rf-depth-select" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; margin-top: -10px;">
                          <option value="None">None</option>
                          <option value="custom">Custom</option>
                      </select>
                  </div>
                  <div id="rf-depth-container" style="display: none; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                      <label for="rf-depth-input" style="text-align: left;">Custom Max Depth:</label>
                      <input type="number" id="rf-depth-input" placeholder="Max depth" min="1" value="1"
                              style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                  </div>
          
                  <!-- Random State -->
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                      <label for="rf-random-state-select" style="flex: 1;">Random State:</label>
                      <select id="rf-random-state-select" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; margin-top: -10px;">
                          <option value="None">None</option>
                          <option value="custom">Custom</option>
                      </select>
                  </div>
                  <div id="rf-random-state-container" style="display: none; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                      <label for="rf-random-state-input" style="text-align: left;">Custom Random State:</label>
                      <input type="number" id="rf-random-state-input" placeholder="Random State" min="0" value="0"
                              style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                  </div>
          
                  <!-- Max Features -->
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                      <label for="rf-max-features-select" style="flex: 1;">Max Features:</label>
                      <select id="rf-max-features-select" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; margin-top: -10px;">
                          <option value="sqrt">Sqrt</option>
                          <option value="auto">Auto</option>
                          <option value="log2">Log2</option>
                          <option value="custom">Custom</option>
                      </select>
                  </div>
                  <div id="rf-max-features-container" style="display: none; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                      <label for="rf-max-features-input" style="text-align: left;">Custom Max Features:</label>
                      <input type="number" id="rf-max-features-input" placeholder="Max Features" min="1" value="1"
                              style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                  </div>
              `;

              const scriptRF = document.createElement('script');
              scriptRF.innerHTML = `
          
                // Función para mostrar/ocultar los inputs personalizados
                function setupDropdownToggle(selectId, containerId) {
                    const select = document.getElementById(selectId);
                    const container = document.getElementById(containerId);
            
                    function updateVisibility() {
                        container.style.display = (select.value === 'custom') ? 'grid' : 'none';
                    }
            
                    select.addEventListener('change', updateVisibility);
                    updateVisibility(); // Ejecutar al cargar
                }
            
                // Aplicar a cada selector
                setupDropdownToggle('rf-depth-select', 'rf-depth-container');
                setupDropdownToggle('rf-random-state-select', 'rf-random-state-container');
                setupDropdownToggle('rf-max-features-select', 'rf-max-features-container');
            
                `;
              document.body.appendChild(scriptRF);
              nameElement = "Random Forest";
              break;
            
            case 'Logistic Regression':
              configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">Logistic Regression Configuration</h3>
                  <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                    <label style="text-align: left;">C: </label>
                    <input type="number" step="0.1" id="logreg-c" value="1.0" min="0.1" id="logreg-c" placeholder="C"
                          style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                  </div>
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                    <label for="logreg-criterion" style="flex: 1; ">Criterion:</label>
                    <select id="logreg-criterion" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box;">
                      <option value="gini">Gini</option>
                      <option value="entropy">Entropy</option>
                      <option value="log_loss">Cross-Entropy Loss</option>
                    </select>
                  </div>

                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                    <label for="logreg-penalty" style="flex: 1; ">Penalty:</label>
                    <select id="logreg-penalty" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box;">
                        <option value="l2">L2</option>
                        <option value="l1">L1</option>
                        <option value="elasticnet">Elasticnet</option>
                        <option value="None">None</option>
                    </select>
                  </div>

                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                    <label for="logreg-solver" style="flex: 1; ">Solver:</label>
                    <select id="logreg-solver" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box;">
                        <option value="lbfgs">Lbfgs</option>
                        <option value="liblinear">Liblinear</option>
                        <option value="newton-cg">Newton Cg</option>
                        <option value="newton-cholesky">Newton Cholesky</option>
                        <option value="sag">Sag</option>
                        <option value="saga">Saga</option>
                    </select>
                  </div>

                  <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                    <label style="text-align: left;">Maximum Iterations: </label>
                    <input type="number" id="logreg-maxiter" value="100" min="1" id="logreg-maxiter" placeholder="Maximum Iterations"
                          style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                  </div>
              `;
              nameElement = "Logistic Regression";
              break;
              case 'SVM':
                configContent.innerHTML = `
                    <h3 style="margin-bottom: 40px;">SVM Configuration</h3>
                    <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                        <label for="svm-kernel" style="flex: 1; ">Kernel:</label>
                        <select id="svm-kernel" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box;">
                            <option value="rbf">RBF</option>
                            <option value="linear">Linear</option>
                            <option value="poly">Polynomial</option>
                            <option value="sigmoid">Sigmoid</option>
                            <option value="precomputed">Precomputed</option>
                        </select>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                        <label style="text-align: left;">C: </label>
                        <input type="number" step="0.1" id="svm-c" value="1.0" min="0.1" placeholder="C"
                               style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                    </div>
                    <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                        <label for="svm-class_weight" style="flex: 1; ">Class Weight:</label>
                        <select id="svm-class_weight" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box;">
                            <option value="None" selected>None</option>
                            <option value="balanced">Balanced</option>
                        </select>
                    </div>
                    <div id="gamma-container" style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                        <label for="svm-gamma" style="flex: 1; ">Gamma:</label>
                        <select id="svm-gamma" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; box-sizing: border-box;">
                            <option value="scale"selected>Scale</option>
                            <option value="auto">Auto</option>
                        </select>
                    </div>
                `;
            
                // Crear el script dinámicamente
                const scriptSVM = document.createElement('script');
                scriptSVM.innerHTML = `
                    const kernelSelect = document.getElementById('svm-kernel');
                    const gammaContainer = document.getElementById('gamma-container');
                    
                    function updateGammaVisibility() {
                        const kernel = kernelSelect.value;
                        gammaContainer.style.display = (kernel === 'rbf' || kernel === 'poly' || kernel === 'sigmoid') ? 'flex' : 'none';
                    }
                    
                    kernelSelect.addEventListener('change', updateGammaVisibility);
                    updateGammaVisibility(); // Ejecutar al cargar
                `;
                document.body.appendChild(scriptSVM);
                nameElement = "SVM";
                break;
            
                case 'Gradient Boosting':
                  configContent.innerHTML = `
                    <h3 style="margin-bottom: 40px;">Gradient Boosting Configuration</h3>
            
                    <!-- Number of Estimators -->
                    <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                        <label style="text-align: left;">Number of Estimators: </label>
                        <input type="number" id="gb-n_estimators" placeholder="Number of estimators" value="100" min="1"
                               style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                    </div>
            
                    <!-- Learning Rate -->
                    <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                        <label style="text-align: left;">Learning Rate: </label>
                        <input type="number" id="gb-learning_rate" placeholder="Learning rate" step="0.1" value="0.1" min="0.0" 
                               style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                    </div>
            
                    <!-- Max Depth -->
                    <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                        <label for="gb-depth-select" style="flex: 1;">Max Depth:</label>
                        <select id="gb-depth-select" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; margin-top: -10px;">
                            <option value="None">None</option>
                            <option value="custom">Custom</option>
                        </select>
                    </div>
                    <div id="gb-depth-container" style="display: none; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                        <label for="gb-depth-input" style="text-align: left;">Custom Max Depth:</label>
                        <input type="number" id="gb-depth-input" placeholder="Max depth" min="1" value="3"
                               style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                    </div>
            
                    <!-- Random State -->
                    <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                        <label for="gb-random-state-select" style="flex: 1;">Random State:</label>
                        <select id="gb-random-state-select" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; margin-top: -10px;">
                            <option value="None">None</option>
                            <option value="custom">Custom</option>
                        </select>
                    </div>
                    <div id="gb-random-state-container" style="display: none; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
                        <label for="gb-random-state-input" style="text-align: left;">Custom Random State:</label>
                        <input type="number" id="gb-random-state-input" placeholder="Random State" min="0" value="0"
                               style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
                    </div>
                  `;
              
                  // Script para mostrar/ocultar los inputs personalizados
                  const scriptGB = document.createElement('script');
                  scriptGB.innerHTML = `
                    function setupDropdownToggle(selectId, containerId) {
                        const select = document.getElementById(selectId);
                        const container = document.getElementById(containerId);
            
                        function updateVisibility() {
                            container.style.display = (select.value === 'custom') ? 'grid' : 'none';
                        }
            
                        select.addEventListener('change', updateVisibility);
                        updateVisibility(); // Ejecutar al cargar
                    }
            
                    setupDropdownToggle('gb-depth-select', 'gb-depth-container');
                    setupDropdownToggle('gb-random-state-select', 'gb-random-state-container');
                  `;
              
                  document.body.appendChild(scriptGB);
                  nameElement = "Gradient Boosting";
                  break;
              
              case 'Decision Tree':
                configContent.innerHTML = `
                  <h3 style="margin-bottom: 40px;">Decision Tree Configuration</h3>
          
                  <!-- Criterion -->
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                      <label for="dt-criterion" style="flex: 1;">Criterion:</label>
                      <select id="dt-criterion" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2;">
                          <option value="gini">Gini</option>
                          <option value="entropy">Entropy</option>
                          <option value="log_loss">Cross-Entropy Loss</option>
                      </select>
                  </div>
          
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
                      <label for="dt-splitter" style="flex: 1;">Splitter:</label>
                      <select id="dt-splitter" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2;">
                          <option value="best">Best</option>
                          <option value="random">Random</option>
                      </select>
                  </div>
          
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                      <label for="dt-max-depth-select" style="flex: 1;">Max Depth:</label>
                      <select id="dt-max-depth-select" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; margin-top: -5px;">
                          <option value="None">None</option>
                          <option value="custom">Custom</option>
                      </select>
                  </div>
                  <div id="dt-max-depth-container" style="display: none; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center; margin-top: -5px;">
                      <label for="dt-max-depth-input" style="text-align: left;">Custom Depth:</label>
                      <input type="number" id="dt-max-depth-input" placeholder="Max depth" min="1" value="1"
                              style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px;">
                  </div>
          
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                      <label for="dt-max-features-select" style="flex: 1;">Max Features:</label>
                      <select id="dt-max-features-select" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; margin-top: -5px;">
                          <option value="None">None</option>
                          <option value="sqrt">Sqrt</option>
                          <option value="log2">Log2</option>
                          <option value="custom">Custom</option>
                      </select>
                  </div>
                  <div id="dt-max-features-container" style="display: none; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center; margin-top: -5px;">
                      <label for="dt-max-features-input" style="text-align: left;">Custom Features:</label>
                      <input type="number" id="dt-max-features-input" placeholder="Max Features" min="1" value="1"
                              style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px;">
                  </div>
          
                  <!-- Random State -->
                  <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: center;">
                      <label for="dt-random-state-select" style="flex: 1;">Random State:</label>
                      <select id="dt-random-state-select" style="height: 3.6em; padding: 0.75em 1em; font-size: 100px; line-height: 1.2; flex: 2; margin-top: -5px;">
                          <option value="None">None</option>
                          <option value="custom">Custom</option>
                      </select>
                  </div>
                  <div id="dt-random-state-container" style="display: none; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center; margin-top: -5px;">
                      <label for="dt-random-state-input" style="text-align: left;">Custom State:</label>
                      <input type="number" id="dt-random-state-input" placeholder="Random State" min="0" value="0"
                              style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px;">
                  </div>
                `;
                const scriptDT = document.createElement('script');
                scriptDT.innerHTML = `
                  // Función para mostrar/ocultar los inputs personalizados
                  function setupDropdownToggle(selectId, containerId) {
                      const select = document.getElementById(selectId);
                      const container = document.getElementById(containerId);
              
                      function updateVisibility() {
                          container.style.display = (select.value === 'custom') ? 'grid' : 'none';
                      }
              
                      select.addEventListener('change', updateVisibility);
                      updateVisibility(); // Ejecutar al cargar
                  }
              
                  // Aplicar la función a cada selector relevante
                  setupDropdownToggle('dt-max-depth-select', 'dt-max-depth-container');
                  setupDropdownToggle('dt-max-features-select', 'dt-max-features-container');
                  setupDropdownToggle('dt-random-state-select', 'dt-random-state-container');
            
                `;
                document.body.appendChild(scriptDT);
                nameElement = "Decision Tree";
                break;
            
            
            default:
              configContent.innerHTML = '<h3>Configuration</h3><p>Unknown configuration content.</p>';
            break;            
          }
          if (nameElement) {
            this.saveParameters(selectedElement, nameElement);
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

  saveParameters(selectedElement: HTMLElement, nameElement: string): void {
    const elementId = selectedElement.id;
      if (!this.elementParameters[elementId]) {
        this.elementParameters[elementId] = {};
      }
      const params = this.elementParameters[elementId];

      switch (nameElement) {
        case 'Standard Scaler':
          // Inicializar valores
          const withMeanSelect = document.getElementById('standard-with-mean') as HTMLSelectElement;
          const withStdSelect = document.getElementById('standard-with-std') as HTMLSelectElement;

          withMeanSelect.value = params.withMean ?? 'True';
          withStdSelect.value = params.withStd ?? 'True';

          this.elementParameters[elementId] = {
            ...this.elementParameters[elementId],
            withMean: withMeanSelect.value,
            withStd: withStdSelect.value
          };

          withMeanSelect.addEventListener('change', () => {
            this.elementParameters[elementId].withMean = withMeanSelect.value;
          });

          withStdSelect.addEventListener('change', () => {
            this.elementParameters[elementId].withStd = withStdSelect.value;
          });
          break;
        case 'MinMax Scaler':
          // Inicializar valores
          const minValueInput = document.getElementById('minmax-min') as HTMLInputElement;
          const maxValueInput = document.getElementById('minmax-max') as HTMLInputElement;
          const clipSelect = document.getElementById('minmax-clip') as HTMLSelectElement;

          minValueInput.value = params.minValue ?? '0';
          maxValueInput.value = params.maxValue ?? '1';
          clipSelect.value = params.clip ?? 'False';

          this.elementParameters[elementId] = {
              ...this.elementParameters[elementId],
              minValue: minValueInput.value,
              maxValue: maxValueInput.value,
              clip: clipSelect.value
          };

          minValueInput.addEventListener('input', () => {
              this.elementParameters[elementId].minValue = minValueInput.value;
          });

          maxValueInput.addEventListener('input', () => {
              this.elementParameters[elementId].maxValue = maxValueInput.value;
          });

          clipSelect.addEventListener('change', () => {
              this.elementParameters[elementId].clip = clipSelect.value;
          });
          break;
        case 'One-Hot Encoding':
          // Inicializar valores
          const handleUnknownSelect = document.getElementById('onehot-handle') as HTMLSelectElement;
          const dropSelect = document.getElementById('onehot-drop') as HTMLSelectElement;

          handleUnknownSelect.value = params.handleUnknown ?? 'error';
          dropSelect.value = params.drop ?? 'None';

          this.elementParameters[elementId] = {
              ...this.elementParameters[elementId],
              handleUnknown: handleUnknownSelect.value,
              drop: dropSelect.value
          };

          handleUnknownSelect.addEventListener('change', () => {
              this.elementParameters[elementId].handleUnknown = handleUnknownSelect.value;
          });

          dropSelect.addEventListener('change', () => {
              this.elementParameters[elementId].drop = dropSelect.value;
          });
          break;

        case 'PCA':
          // Inicializar valores
          const componentsSelect = document.getElementById('pca-components-select') as HTMLSelectElement;
          const componentsContainer = document.getElementById('pca-components-container') as HTMLElement;
          const componentsInput = document.getElementById('pca-components-input') as HTMLInputElement;
          const whitenSelect = document.getElementById('pca-whiten') as HTMLSelectElement;
      
          componentsSelect.value = params.componentsOption ?? 'None';
          componentsInput.value = params.customComponents ?? '1';
          whitenSelect.value = params.whiten ?? 'False';
      
          // Mostrar u ocultar el input de componentes según la selección
          if (componentsSelect.value === 'custom') {
              componentsContainer.style.display = 'grid';
          }
      
          // Inicializar los parámetros
          this.elementParameters[elementId] = {
              ...this.elementParameters[elementId],
              componentsOption: componentsSelect.value,
              whiten: whitenSelect.value
          };
      
          componentsSelect.addEventListener('change', () => {
              this.elementParameters[elementId].componentsOption = componentsSelect.value;
      
              // Mostrar u ocultar el input de componentes según la selección
              if (componentsSelect.value === 'custom') {
                  componentsContainer.style.display = 'grid';
      
                  // Guardar customComponents solo si 'custom' está seleccionado
                  this.elementParameters[elementId].customComponents = componentsInput.value;
              } else {
                  componentsContainer.style.display = 'none';
      
                  // No guardar customComponents si 'None' está seleccionado
                  delete this.elementParameters[elementId].customComponents;
              }
          });
      
          componentsInput.addEventListener('input', () => {
              // Guardar el valor de customComponents solo si 'custom' está seleccionado
              if (componentsSelect.value === 'custom') {
                  this.elementParameters[elementId].customComponents = componentsInput.value;
              }
          });
      
          whitenSelect.addEventListener('change', () => {
              this.elementParameters[elementId].whiten = whitenSelect.value;
          });
      
          break;
        

        case 'Normalizer':
          // Obtener el select del Norm
          const normSelect = document.getElementById('normalizer-norm') as HTMLSelectElement;

          // Asignar valor por defecto si no existe
          normSelect.value = params.norm ?? 'l2';

          // Guardar el valor seleccionado
          this.elementParameters[elementId] = {
              ...this.elementParameters[elementId],
              norm: normSelect.value
          };

          // Agregar el event listener
          normSelect.addEventListener('change', () => {
              this.elementParameters[elementId].norm = normSelect.value;
          });
          break;

        case 'KNN Imputer':
          // Obtener los elementos del DOM
          const neighborsInputKNNImputer = document.getElementById('knn-neighbors') as HTMLInputElement;
          const weightSelectKNNImputer = document.getElementById('knn-weight') as HTMLSelectElement;

          // Asignar valores por defecto si no existen
          neighborsInputKNNImputer.value = params.neighbors ?? '5';
          weightSelectKNNImputer.value = params.weight ?? 'uniform';

          // Guardar los valores
          this.elementParameters[elementId] = {
              ...this.elementParameters[elementId],
              neighbors: neighborsInputKNNImputer.value,
              weight: weightSelectKNNImputer.value
          };

          // Event listeners
          neighborsInputKNNImputer.addEventListener('input', () => {
              this.elementParameters[elementId].neighbors = neighborsInputKNNImputer.value;
          });

          weightSelectKNNImputer.addEventListener('change', () => {
              this.elementParameters[elementId].weight = weightSelectKNNImputer.value;
          });
          break;

        case 'KNN':
          // Obtener los elementos del DOM
          const neighborsInput = document.getElementById('knn-neighbors') as HTMLInputElement;
          const weightSelect = document.getElementById('knn-weight') as HTMLSelectElement;
          const algorithmSelect = document.getElementById('knn-algorithm') as HTMLSelectElement;
          const metricSelect = document.getElementById('knn-metric') as HTMLSelectElement;

          // Asignar valores por defecto si no existen
          neighborsInput.value = params.neighbors ?? '5';
          weightSelect.value = params.weight ?? 'uniform';
          algorithmSelect.value = params.algorithm ?? 'auto';
          metricSelect.value = params.metric ?? 'minkowski';

          // Guardar los valores
          this.elementParameters[elementId] = {
              ...this.elementParameters[elementId],
              neighbors: neighborsInput.value,
              weight: weightSelect.value,
              algorithm: algorithmSelect.value,
              metric: metricSelect.value
          };

          // Agregar event listeners
          neighborsInput.addEventListener('input', () => {
              this.elementParameters[elementId].neighbors = neighborsInput.value;
          });

          weightSelect.addEventListener('change', () => {
              this.elementParameters[elementId].weight = weightSelect.value;
          });

          algorithmSelect.addEventListener('change', () => {
              this.elementParameters[elementId].algorithm = algorithmSelect.value;
          });

          metricSelect.addEventListener('change', () => {
              this.elementParameters[elementId].metric = metricSelect.value;
          });
          break;

        case 'Random Forest':
          // Inicializar valores
          const treesInput = document.getElementById('rf-trees') as HTMLInputElement;
          const depthSelect = document.getElementById('rf-depth-select') as HTMLSelectElement;
          const depthContainer = document.getElementById('rf-depth-container') as HTMLElement;
          const depthInput = document.getElementById('rf-depth-input') as HTMLInputElement;
          const randomStateSelect = document.getElementById('rf-random-state-select') as HTMLSelectElement;
          const randomStateContainer = document.getElementById('rf-random-state-container') as HTMLElement;
          const randomStateInput = document.getElementById('rf-random-state-input') as HTMLInputElement;
          const maxFeaturesSelect = document.getElementById('rf-max-features-select') as HTMLSelectElement;
          const maxFeaturesContainer = document.getElementById('rf-max-features-container') as HTMLElement;
          const maxFeaturesInput = document.getElementById('rf-max-features-input') as HTMLInputElement;
      
          treesInput.value = params.trees ?? '100';
          depthSelect.value = params.depthOption ?? 'None';
          depthInput.value = params.customDepth ?? '1';
          randomStateSelect.value = params.randomStateOption ?? 'None';
          randomStateInput.value = params.customRandomState ?? '0';
          maxFeaturesSelect.value = params.maxFeaturesOption ?? 'sqrt';
          maxFeaturesInput.value = params.customMaxFeatures ?? '1';
      
          // Mostrar u ocultar los inputs personalizados
          if (depthSelect.value === 'custom') {
              depthContainer.style.display = 'grid';
          }
          if (randomStateSelect.value === 'custom') {
              randomStateContainer.style.display = 'grid';
          }
          if (maxFeaturesSelect.value === 'custom') {
              maxFeaturesContainer.style.display = 'grid';
          }
      
          // Inicializar los parámetros
          this.elementParameters[elementId] = {
              ...this.elementParameters[elementId],
              trees: treesInput.value,
              depthOption: depthSelect.value,
              randomStateOption: randomStateSelect.value,
              maxFeaturesOption: maxFeaturesSelect.value
          };
      
          depthSelect.addEventListener('change', () => {
              this.elementParameters[elementId].depthOption = depthSelect.value;
              if (depthSelect.value === 'custom') {
                  depthContainer.style.display = 'grid';
                  this.elementParameters[elementId].customDepth = depthInput.value;
              } else {
                  depthContainer.style.display = 'none';
                  delete this.elementParameters[elementId].customDepth;
              }
          });
      
          randomStateSelect.addEventListener('change', () => {
              this.elementParameters[elementId].randomStateOption = randomStateSelect.value;
              if (randomStateSelect.value === 'custom') {
                  randomStateContainer.style.display = 'grid';
                  this.elementParameters[elementId].customRandomState = randomStateInput.value;
              } else {
                  randomStateContainer.style.display = 'none';
                  delete this.elementParameters[elementId].customRandomState;
              }
          });
      
          maxFeaturesSelect.addEventListener('change', () => {
              this.elementParameters[elementId].maxFeaturesOption = maxFeaturesSelect.value;
              if (maxFeaturesSelect.value === 'custom') {
                  maxFeaturesContainer.style.display = 'grid';
                  this.elementParameters[elementId].customMaxFeatures = maxFeaturesInput.value;
              } else {
                  maxFeaturesContainer.style.display = 'none';
                  delete this.elementParameters[elementId].customMaxFeatures;
              }
          });
      
          treesInput.addEventListener('input', () => {
              this.elementParameters[elementId].trees = treesInput.value;
          });
      
          depthInput.addEventListener('input', () => {
              if (depthSelect.value === 'custom') {
                  this.elementParameters[elementId].customDepth = depthInput.value;
              }
          });
      
          randomStateInput.addEventListener('input', () => {
              if (randomStateSelect.value === 'custom') {
                  this.elementParameters[elementId].customRandomState = randomStateInput.value;
              }
          });
      
          maxFeaturesInput.addEventListener('input', () => {
              if (maxFeaturesSelect.value === 'custom') {
                  this.elementParameters[elementId].customMaxFeatures = maxFeaturesInput.value;
              }
          });
      
          break;

        case 'Logistic Regression':
          const cInputLR =  document.getElementById('logreg-c') as HTMLInputElement;
          const criterionSelect =  document.getElementById('logreg-criterion') as HTMLInputElement;
          const penaltySelect =  document.getElementById('logreg-penalty') as HTMLInputElement;
          const solverSelect =  document.getElementById('logreg-solver') as HTMLInputElement;
          const maxIterInput =  document.getElementById('logreg-maxiter') as HTMLInputElement;
          
          // Inicializar valores de configuración (si están disponibles)
          cInputLR.value = params.c ?? '1.0';
          criterionSelect.value = params.criterion ?? 'gini';
          penaltySelect.value = params.penalty ?? 'l2';
          solverSelect.value = params.solver ?? 'lbfgs';
          maxIterInput.value = params.maxIter ?? '100';
          
          // Guardar parámetros de configuración
          this.elementParameters[elementId] = {
              ...this.elementParameters[elementId],
              c: cInputLR.value,
              criterion: criterionSelect.value,
              penalty: penaltySelect.value,
              solver: solverSelect.value,
              maxIter: maxIterInput.value
          };

          // Escuchar cambios y actualizar los parámetros
          cInputLR.addEventListener('input', () => {
              this.elementParameters[elementId].c = cInputLR.value;
          });

          criterionSelect.addEventListener('change', () => {
            this.elementParameters[elementId].criterion = criterionSelect.value;
          });
          
          penaltySelect.addEventListener('change', () => {
              this.elementParameters[elementId].penalty = penaltySelect.value;
          });
          
          solverSelect.addEventListener('change', () => {
              this.elementParameters[elementId].solver = solverSelect.value;
          });
          
          maxIterInput.addEventListener('input', () => {
              this.elementParameters[elementId].maxIter = maxIterInput.value;
          });

          break;
        
        case 'Gradient Boosting':
          const nEstimatorsInput = document.getElementById('gb-n_estimators') as HTMLInputElement;
          const learningRateInput = document.getElementById('gb-learning_rate') as HTMLInputElement;
          const depthSelectGB = document.getElementById('gb-depth-select') as HTMLSelectElement;
          const depthContainerGB = document.getElementById('gb-depth-container') as HTMLElement;
          const depthInputGB = document.getElementById('gb-depth-input') as HTMLInputElement;
          const randomStateSelectGB = document.getElementById('gb-random-state-select') as HTMLSelectElement;
          const randomStateContainerGB = document.getElementById('gb-random-state-container') as HTMLElement;
          const randomStateInputGB = document.getElementById('gb-random-state-input') as HTMLInputElement;
      
          // Inicializar los valores de los parámetros
          nEstimatorsInput.value = params.n_estimators ?? '100';
          learningRateInput.value = params.learning_rate ?? '0.1';
          depthSelectGB.value = params.max_depth ?? 'None';
          depthInputGB.value = params.customMaxDepth ?? '3';
          randomStateSelectGB.value = params.random_state ?? 'None';
          randomStateInputGB.value = params.customRandomState ?? '0';
      
          // Mostrar u ocultar el input de Max Depth según la selección
          if (depthSelectGB.value === 'custom') {
              depthContainerGB.style.display = 'grid';
          } else {
              depthContainerGB.style.display = 'none';
          }
      
          // Mostrar u ocultar el input de Random State según la selección
          if (randomStateSelectGB.value === 'custom') {
              randomStateContainerGB.style.display = 'grid';
          } else {
              randomStateContainerGB.style.display = 'none';
          }
      
          // Inicializar los parámetros
          this.elementParameters[elementId] = {
              ...this.elementParameters[elementId],
              n_estimators: nEstimatorsInput.value,
              learning_rate: learningRateInput.value,
              max_depth: depthSelectGB.value,
              random_state: randomStateSelectGB.value
          };
      
          // Event listener para el selector de Max Depth
          depthSelectGB.addEventListener('change', () => {
              this.elementParameters[elementId].max_depth = depthSelectGB.value;
      
              // Mostrar u ocultar el input de Max Depth según la selección
              if (depthSelectGB.value === 'custom') {
                  depthContainerGB.style.display = 'grid';
                  // Guardar el customMaxDepth solo si 'custom' está seleccionado
                  this.elementParameters[elementId].customMaxDepth = depthInputGB.value;
              } else {
                  depthContainerGB.style.display = 'none';
                  // No guardar customMaxDepth si 'none' está seleccionado
                  delete this.elementParameters[elementId].customMaxDepth;
              }
          });
      
          // Event listener para el input de Max Depth
          depthInputGB.addEventListener('input', () => {
              // Guardar el valor de customMaxDepth solo si 'custom' está seleccionado
              if (depthSelectGB.value === 'custom') {
                  this.elementParameters[elementId].customMaxDepth = depthInputGB.value;
              }
          });
      
          // Event listener para el selector de Random State
          randomStateSelectGB.addEventListener('change', () => {
              this.elementParameters[elementId].random_state = randomStateSelectGB.value;
      
              // Mostrar u ocultar el input de Random State según la selección
              if (randomStateSelectGB.value === 'custom') {
                  randomStateContainerGB.style.display = 'grid';
                  // Guardar customRandomState solo si 'custom' está seleccionado
                  this.elementParameters[elementId].customRandomState = randomStateInputGB.value;
              } else {
                  randomStateContainerGB.style.display = 'none';
                  // No guardar customRandomState si 'none' está seleccionado
                  delete this.elementParameters[elementId].customRandomState;
              }
          });
      
          // Event listener para el input de Random State
          randomStateInputGB.addEventListener('input', () => {
              // Guardar el valor de customRandomState solo si 'custom' está seleccionado
              if (randomStateSelectGB.value === 'custom') {
                  this.elementParameters[elementId].customRandomState = randomStateInputGB.value;
              }
          });
      
          // Event listener para el input de Número de Estimadores
          nEstimatorsInput.addEventListener('input', () => {
              this.elementParameters[elementId].n_estimators = nEstimatorsInput.value;
          });
      
          // Event listener para el input de Learning Rate
          learningRateInput.addEventListener('input', () => {
              this.elementParameters[elementId].learning_rate = learningRateInput.value;
          });
      
          break;

        case 'Decision Tree':
          // Inicializar valores
          const criterionSelectDT = document.getElementById('dt-criterion') as HTMLSelectElement;
          const splitterSelectDT = document.getElementById('dt-splitter') as HTMLSelectElement;
          const maxDepthSelectDT = document.getElementById('dt-max-depth-select') as HTMLSelectElement;
          const maxDepthContainerDT = document.getElementById('dt-max-depth-container') as HTMLElement;
          const maxDepthInputDT = document.getElementById('dt-max-depth-input') as HTMLInputElement;
          const maxFeaturesSelectDT = document.getElementById('dt-max-features-select') as HTMLSelectElement;
          const maxFeaturesContainerDT = document.getElementById('dt-max-features-container') as HTMLElement;
          const maxFeaturesInputDT = document.getElementById('dt-max-features-input') as HTMLInputElement;
          const randomStateSelectDT = document.getElementById('dt-random-state-select') as HTMLSelectElement;
          const randomStateContainerDT = document.getElementById('dt-random-state-container') as HTMLElement;
          const randomStateInputDT = document.getElementById('dt-random-state-input') as HTMLInputElement;
      
          // Inicializar los valores de los parámetros
          criterionSelectDT.value = params.criterion ?? 'gini';
          splitterSelectDT.value = params.splitter ?? 'best';
          maxDepthSelectDT.value = params.max_depth ?? 'None';
          maxDepthInputDT.value = params.customMaxDepth ?? '1';
          maxFeaturesSelectDT.value = params.max_features ?? 'None';
          maxFeaturesInputDT.value = params.customMaxFeatures ?? '1';
          randomStateSelectDT.value = params.random_state ?? 'None';
          randomStateInputDT.value = params.customRandomState ?? '0';
      
          // Mostrar u ocultar el input de Max Depth según la selección
          if (maxDepthSelectDT.value === 'custom') {
              maxDepthContainerDT.style.display = 'grid';
          } else {
              maxDepthContainerDT.style.display = 'none';
          }
      
          // Mostrar u ocultar el input de Max Features según la selección
          if (maxFeaturesSelectDT.value === 'custom') {
              maxFeaturesContainerDT.style.display = 'grid';
          } else {
              maxFeaturesContainerDT.style.display = 'none';
          }
      
          // Mostrar u ocultar el input de Random State según la selección
          if (randomStateSelectDT.value === 'custom') {
              randomStateContainerDT.style.display = 'grid';
          } else {
              randomStateContainerDT.style.display = 'none';
          }
      
          // Inicializar los parámetros
          this.elementParameters[elementId] = {
              ...this.elementParameters[elementId],
              criterion: criterionSelectDT.value,
              splitter: splitterSelectDT.value,
              max_depth: maxDepthSelectDT.value,
              max_features: maxFeaturesSelectDT.value,
              random_state: randomStateSelectDT.value
          };
      
          // Event listener para el selector de Max Depth
          maxDepthSelectDT.addEventListener('change', () => {
              this.elementParameters[elementId].max_depth = maxDepthSelectDT.value;
      
              // Mostrar u ocultar el input de Max Depth según la selección
              if (maxDepthSelectDT.value === 'custom') {
                  maxDepthContainerDT.style.display = 'grid';
                  // Guardar el customMaxDepth solo si 'custom' está seleccionado
                  this.elementParameters[elementId].customMaxDepth = maxDepthInputDT.value;
              } else {
                  maxDepthContainerDT.style.display = 'none';
                  // No guardar customMaxDepth si 'none' está seleccionado
                  delete this.elementParameters[elementId].customMaxDepth;
              }
          });
      
          // Event listener para el input de Max Depth
          maxDepthInputDT.addEventListener('input', () => {
              // Guardar el valor de customMaxDepth solo si 'custom' está seleccionado
              if (maxDepthSelectDT.value === 'custom') {
                  this.elementParameters[elementId].customMaxDepth = maxDepthInputDT.value;
              }
          });
      
          // Event listener para el selector de Max Features
          maxFeaturesSelectDT.addEventListener('change', () => {
              this.elementParameters[elementId].max_features = maxFeaturesSelectDT.value;
      
              // Mostrar u ocultar el input de Max Features según la selección
              if (maxFeaturesSelectDT.value === 'custom') {
                  maxFeaturesContainerDT.style.display = 'grid';
                  // Guardar el customMaxFeatures solo si 'custom' está seleccionado
                  this.elementParameters[elementId].customMaxFeatures = maxFeaturesInputDT.value;
              } else {
                  maxFeaturesContainerDT.style.display = 'none';
                  // No guardar customMaxFeatures si 'none' está seleccionado
                  delete this.elementParameters[elementId].customMaxFeatures;
              }
          });
      
          // Event listener para el input de Max Features
          maxFeaturesInputDT.addEventListener('input', () => {
              // Guardar el valor de customMaxFeatures solo si 'custom' está seleccionado
              if (maxFeaturesSelectDT.value === 'custom') {
                  this.elementParameters[elementId].customMaxFeatures = maxFeaturesInputDT.value;
              }
          });
      
          // Event listener para el selector de Random State
          randomStateSelectDT.addEventListener('change', () => {
              this.elementParameters[elementId].random_state = randomStateSelectDT.value;
      
              // Mostrar u ocultar el input de Random State según la selección
              if (randomStateSelectDT.value === 'custom') {
                  randomStateContainerDT.style.display = 'grid';
                  // Guardar customRandomState solo si 'custom' está seleccionado
                  this.elementParameters[elementId].customRandomState = randomStateInputDT.value;
              } else {
                  randomStateContainerDT.style.display = 'none';
                  // No guardar customRandomState si 'none' está seleccionado
                  delete this.elementParameters[elementId].customRandomState;
              }
          });
      
          // Event listener para el input de Random State
          randomStateInputDT.addEventListener('input', () => {
              // Guardar el valor de customRandomState solo si 'custom' está seleccionado
              if (randomStateSelectDT.value === 'custom') {
                  this.elementParameters[elementId].customRandomState = randomStateInputDT.value;
              }
          });
      
          // Event listener para el selector de Criterion
          criterionSelectDT.addEventListener('change', () => {
              this.elementParameters[elementId].criterion = criterionSelectDT.value;
          });
      
          // Event listener para el selector de Splitter
          splitterSelectDT.addEventListener('change', () => {
              this.elementParameters[elementId].splitter = splitterSelectDT.value;
          });
      
          break;
        

        default:
          

      }


      
  }

  saveScenario(): void {
    const savedElements = this.droppedElements.map((element: HTMLElement) => ({
      id: element.id,
      type: element.getAttribute('data-type'),
      position: {
        left: element.offsetLeft,
        top: element.offsetTop,
      },
      parameters: this.elementParameters[element.id] || {}
    }));
  
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
