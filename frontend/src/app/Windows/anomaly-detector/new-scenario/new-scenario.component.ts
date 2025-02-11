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

  scenario: Scenario | null = null;  // Puedes inicializarla como null

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

  zoomLevel: number = 1; // Nivel de zoom por defecto
  zoomStep: number = 0.02; // Cuánto aumenta o disminuye el zoom
  minZoom: number = 0.3;  // Mínimo nivel de zoom
  maxZoom: number = 1.08;    // Máximo nivel de zoom

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

      // Registrar suscripción para guardar
      this.scenarioService.saveRequested$.subscribe(() => this.saveScenario());
      
      // Actualizar estado cuando cambian los elementos
      this.scenarioService.setUnsavedChanges(this.droppedElements.length > 0);

      // Obtener el parámetro 'id' de la ruta
      this.scenarioId = this.route.snapshot.paramMap.get('id');

      if (this.scenarioId) {
        // Si 'id' está presente, es una edición
        this.isNewScenario = false;
        this.loadEditScenario(this.scenarioId);
      } 
    }
  }

  updateUnsavedState() {
    // Enviar el estado actual al servicio
    this.scenarioService.setUnsavedChanges(this.droppedElements.length > 0);
  }

  toggleSection(section: 'dataSource' | 'dataProcessing' | 'dataModel') {
    this.activeSections[section] = !this.activeSections[section];
  }

  addDragEventListeners() {
    const draggableElements = document.querySelectorAll('.option');
  
    draggableElements.forEach((element: Element) => {
      // Aseguramos que el elemento es de tipo HTMLElement
      const htmlElement = element as HTMLElement;
  
      // Ahora puedes usar los métodos y propiedades específicos de HTMLElement
      htmlElement.addEventListener('dragstart', (event) => this.onDragStart(event, false));
      htmlElement.addEventListener('dragend', (event) => this.onDragEnd(event));
    });
  }
  

  // Detectar clics en los elementos para seleccionar
  onElementClick(event: MouseEvent, element: EventTarget | null): void {
    // Verificar si el clic fue en los iconos (rueda o flecha)
    if (element instanceof HTMLElement && (element.classList.contains('gear-icon') || element.classList.contains('arrow-icon'))) {
      // Si fue clic en la rueda o la flecha, no hacer nada para evitar la selección
      event.stopPropagation(); // Evitar que el clic se propague a otros elementos
      return;
    }
  
    // Si estamos en modo de conexión, procesar la conexión
    if (this.isConnecting && this.connectionStartElement) {
      if (element instanceof HTMLElement) {
        // Crear la conexión entre `connectionStartElement` y el elemento seleccionado
        this.createConnection(this.connectionStartElement, element);
  
        // Finalizar el modo de conexión
        this.isConnecting = false;
        this.connectionStartElement = null;
      }
      return;
    }
  
    // Lógica para la selección de elementos
    event.stopPropagation(); // Evitar que el clic se propague
  
    if (element instanceof HTMLElement) {
      const isCtrlOrCmdPressed = event.ctrlKey || event.metaKey;
  
      if (isCtrlOrCmdPressed) {
        // Si el elemento ya está seleccionado, deseleccionarlo
        if (this.selectedElements.includes(element)) {
          this.deselectElement(element);
        } else {
          // Agregar a la selección
          this.selectElement(element);
        }
      } else {
        // Seleccionar solo este elemento
        this.clearSelection();
        this.selectElement(element);
      }
    }
  }

  // Seleccionar un elemento
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
  
  // Limpiar la selección de todos los elementos
  clearSelection() {
    this.selectedElements.forEach((el) => el.classList.remove('selected'));
    this.selectedElements = [];
  }

  // Detectar clic fuera de los elementos seleccionados para deseleccionarlos
  onDocumentClick(event: MouseEvent) {
    // Verificamos si el clic fue fuera de los elementos seleccionados
    if (!this.selectedElements.some((element) => element.contains(event.target as Node))) {
      this.clearSelection(); // Limpiamos la selección si no se hizo clic dentro de los elementos seleccionados
    }
  
    const menu = document.getElementById('context-menu');
    if (menu && !menu.contains(event.target as Node)) {
      this.hideContextMenu();
    }
  }
  

  // Manejo de la tecla "Delete"
  onKeyDown(event: KeyboardEvent): void {
    // Verificar si la tecla presionada es 'Backspace' (retroceso) o 'Delete' (borrar)
    if (event.key === 'Backspace' || event.key === 'Delete') {
      this.deleteSelectedElements();
    }
  }
  
  // Método para eliminar los elementos seleccionados
  deleteSelectedElements(): void {
    if (this.selectedElements.length > 0) {
        // 1. Guardar referencia de los elementos a eliminar
        const elementsToDelete = [...this.selectedElements];

        // Eliminar conexiones
        this.connections = this.connections.filter((connection) => {
            const isConnected = elementsToDelete.includes(connection.startElement) || 
                              elementsToDelete.includes(connection.endElement);
            
            if (isConnected && connection.line.parentElement) {
                connection.line.parentElement.removeChild(connection.line);
            }
            return !isConnected;
        });

        // Eliminar elementos del DOM
        elementsToDelete.forEach(element => {
            if (element.parentElement) {
                element.parentElement.removeChild(element);
            }
        });

        // 2. Actualizar droppedElements ANTES de limpiar selectedElements
        this.droppedElements = this.droppedElements.filter(el => !elementsToDelete.includes(el));
        
        // 3. Ahora sí limpiar la selección
        this.selectedElements = [];
        
        this.updateUnsavedState();
    }
  }

  // Arrastre de los elementos
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
  
      // Calcular las distancias relativas entre los elementos seleccionados
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
    this.draggedElements = []; // Resetear la lista de elementos arrastrados
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
  
    const dropArea = document.getElementById('drop-area');
    if (dropArea) {
      const rect = dropArea.getBoundingClientRect();
      const dropX = (event.clientX - rect.left) / this.zoomLevel;  // Ajustar con el zoom
      const dropY = (event.clientY - rect.top) / this.zoomLevel;  // Ajustar con el zoom
  
      this.relativePositions.forEach(({ element, offsetX, offsetY }) => {
        if (!dropArea.contains(element)) {
          element.id = `element-${this.nextElementId++}`;
          element.addEventListener('click', (e) => this.onElementClick(e, element));
          element.addEventListener('contextmenu', (e) => this.onElementClickWorkspace(e, element));
  
          // Crear el ícono de rueda dentada
          const gearIcon = document.createElement('i');
          gearIcon.className = 'fa fa-cog gear-icon';  // Ajustar la clase para estilo
          gearIcon.style.display = 'none';  // Inicialmente oculto
  
          // Crear la flecha mirando hacia la derecha
          const arrowIcon = document.createElement('i');
          arrowIcon.className = 'fa fa-arrow-right arrow-icon';  // Ajustar clase
          arrowIcon.style.display = 'none';  // Inicialmente oculta
  
          // Mostrar íconos al pasar el ratón sobre el elemento
          element.addEventListener('mouseenter', () => {
            gearIcon.style.display = 'block';
            arrowIcon.style.display = 'block';
          });
  
          // Ocultar íconos al salir del elemento
          element.addEventListener('mouseleave', () => {
            gearIcon.style.display = 'none';
            arrowIcon.style.display = 'none';
          });
  
          // Evitar seleccionar el elemento y ejecutar la acción correspondiente al hacer clic en la rueda dentada
          gearIcon.addEventListener('click', (e) => {
            e.stopPropagation();  // Prevenir selección
            this.onConfigurationClick(element);  // Llamada a la función
          });
  
          // Evitar seleccionar el elemento y ejecutar la acción correspondiente al hacer clic en la flecha
          arrowIcon.addEventListener('click', (e) => {
            e.stopPropagation();  // Prevenir selección
            this.onConnectionClick(element);  // Llamada a la función
          });
  
          // Agregar íconos al elemento
          element.appendChild(gearIcon);
          element.appendChild(arrowIcon);
          dropArea.appendChild(element);
        }
  
        element.style.position = 'absolute';
  
        // Limitar las posiciones X e Y con el zoom
        const maxX = dropArea.offsetWidth / this.zoomLevel - element.offsetWidth;
        let newX = dropX + offsetX;
        newX = Math.max(0, Math.min(newX, maxX));  // Limitar la posición X
  
        const maxY = dropArea.offsetHeight / this.zoomLevel - element.offsetHeight;
        let newY = dropY + offsetY;
        newY = Math.max(0, Math.min(newY, maxY));  // Limitar la posición Y
  
        element.style.left = `${newX * this.zoomLevel}px`;  // Ajustar con el zoom
        element.style.top = `${newY * this.zoomLevel}px`;   // Ajustar con el zoom
  
        // Actualizar conexiones si el elemento está involucrado en alguna
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

  // Detectar cuando el ratón se mueve para seleccionar todos los elementos por encima de ellos
  onMouseMove(event: MouseEvent) {
    const dropArea = document.getElementById('drop-area');
    if (!dropArea) return;
  
    const rect = dropArea.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
  
    // Verificar si el ratón está sobre algún elemento de la cuadrícula
    this.draggedElements = [];
  
    const elements = Array.from(dropArea.querySelectorAll('.option')); // Obtener todos los elementos dentro del área
    elements.forEach((element) => {
      const elRect = element.getBoundingClientRect();
      const elLeft = elRect.left - rect.left;
      const elTop = elRect.top - rect.top;
      const elRight = elLeft + elRect.width;
      const elBottom = elTop + elRect.height;
  
      // Si el mouse está dentro de los límites de un elemento, seleccionamos ese elemento
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
  
    this.clearSelection();  // Limpiar cualquier selección previa
  
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
  
      // Aquí solo seleccionamos elementos, no los deseleccionamos
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
          // Asegúrate de no deseleccionar elementos ya seleccionados
          if (!this.selectedElements.includes(el)) {
            this.selectElement(el);
          }
        } else {
          // Solo deseleccionamos si no está ya deseleccionado
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
  
    // Aplicar la clase .selected a los elementos que están en selectedElements
    this.selectedElements.forEach((el) => {
      el.classList.add('selected');
    });
  
    // No necesitas restablecer la selección aquí, solo ocultar el área de selección
    const selectionBox = document.getElementById('selection-box');
    if (selectionBox) {
      selectionBox.style.display = 'none';
    }
  }
  

  onElementClickWorkspace(event: MouseEvent, element: HTMLElement): void {
    event.preventDefault();  // Evitar el menú contextual predeterminado
    const menu = document.getElementById('context-menu');
    if (menu) {
      // Obtener la posición del clic y mostrar el menú en esa ubicación
      const x = event.clientX;
      const y = event.clientY;
  
      menu.style.left = `${x}px`;
      menu.style.top = `${y}px`;
      menu.style.display = 'block';  // Mostrar el menú
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

    // Asegurarse de que el SVG esté dentro del dropArea
    if (!dropArea.contains(svg)) {
        svg.setAttribute('width', `${dropArea.offsetWidth}`);
        svg.setAttribute('height', `${dropArea.offsetHeight}`);
        svg.style.position = 'absolute';
        svg.style.top = '0';
        svg.style.left = '0';
        svg.style.pointerEvents = 'none'; // No interferir con otros elementos
        dropArea.appendChild(svg);
    }

    // Obtener el nivel de escala (zoom)
    const scale = this.getZoomScale();

    // Obtener las coordenadas de ambos elementos
    const startRect = startElement.getBoundingClientRect();
    const endRect = endElement.getBoundingClientRect();
    const dropAreaRect = dropArea.getBoundingClientRect();

    // Calcular las distancias entre todos los bordes posibles de ambos elementos
    const distances = this.calculateAllDistances(startRect, endRect);

    // Obtener la combinación de bordes con la menor distancia
    const closestPair = this.getClosestPair(distances);

    // Asegurarse de que las coordenadas están relativas al área de trabajo
    if (closestPair.startEdge && closestPair.endEdge) {
        let startX = (closestPair.startEdge.x - dropAreaRect.left) / scale;
        let startY = (closestPair.startEdge.y - dropAreaRect.top) / scale;
        let endX = (closestPair.endEdge.x - dropAreaRect.left) / scale;
        let endY = (closestPair.endEdge.y - dropAreaRect.top) / scale;

        // Ajustar la línea para que no se desplace fuera ni dentro del elemento
        const startElementStyles = window.getComputedStyle(startElement);
        const endElementStyles = window.getComputedStyle(endElement);

        // Ajuste de los bordes según el estilo del elemento
        const startAdjustmentX = parseInt(startElementStyles.borderLeftWidth, 10) || 0;
        const startAdjustmentY = parseInt(startElementStyles.borderTopWidth, 10) || 0;
        const endAdjustmentX = parseInt(endElementStyles.borderLeftWidth, 10) || 0;
        const endAdjustmentY = parseInt(endElementStyles.borderTopWidth, 10) || 0;

        // Corregir la escala para los ajustes de los bordes
        startX += startAdjustmentX / scale;
        startY += startAdjustmentY / scale;
        endX += endAdjustmentX / scale;
        endY += endAdjustmentY / scale;

        // Crear la línea entre los bordes más cercanos
        const line = document.createElementNS(svgNamespace, 'line');
        line.setAttribute('x1', `${startX}`);
        line.setAttribute('y1', `${startY}`);
        line.setAttribute('x2', `${endX}`);
        line.setAttribute('y2', `${endY}`);
        line.setAttribute('stroke', 'black');
        line.setAttribute('stroke-width', '2');

        svg.appendChild(line);

        // Guardar la conexión
        this.connections.push({
            startElement,
            endElement,
            line
        });
    }

    this.isConnecting = false;
    this.connectionStartElement = null;
}


  // Método auxiliar para calcular las distancias entre todos los bordes posibles de ambos elementos
  private calculateAllDistances(startRect: DOMRect, endRect: DOMRect): { startEdge: { x: number, y: number }, endEdge: { x: number, y: number }, distance: number }[] {
      const startEdges = this.getEdges(startRect);
      const endEdges = this.getEdges(endRect);

      const distances: { startEdge: { x: number, y: number }, endEdge: { x: number, y: number }, distance: number }[] = [];
      
      // Calcular la distancia entre todos los bordes
      startEdges.forEach((startEdge) => {
          endEdges.forEach((endEdge) => {
              const distance = Math.hypot(startEdge.x - endEdge.x, startEdge.y - endEdge.y);
              distances.push({ startEdge, endEdge, distance });
          });
      });

      return distances;
  }

  // Método para obtener las coordenadas de los bordes de un rectángulo
  private getEdges(rect: DOMRect): { x: number, y: number }[] {
      const left = { x: rect.left, y: rect.top + rect.height / 2 };     // Medio del borde izquierdo
      const right = { x: rect.right, y: rect.top + rect.height / 2 };    // Medio del borde derecho
      const top = { x: rect.left + rect.width / 2, y: rect.top };        // Medio del borde superior
      const bottom = { x: rect.left + rect.width / 2, y: rect.bottom };  // Medio del borde inferior

      return [top, bottom, left, right];
  }

  // Método para obtener la combinación de bordes con la menor distancia
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
        // Verificar si el elemento es parte de la conexión
        if (connection.startElement === element || connection.endElement === element) {
            const dropArea = document.getElementById('drop-area');
            if (!dropArea) return;

            // Obtener el nivel de escala (zoom)
            const scale = this.getZoomScale();

            const startRect = connection.startElement.getBoundingClientRect();
            const endRect = connection.endElement.getBoundingClientRect();
            const dropAreaRect = dropArea.getBoundingClientRect();

            // Calcular las distancias entre todos los bordes posibles de ambos elementos
            const distances = this.calculateAllDistances(startRect, endRect);

            // Obtener la combinación de bordes con la menor distancia
            const closestPair = this.getClosestPair(distances);

            // Asegurarse de que las coordenadas están relativas al área de trabajo
            if (closestPair.startEdge && closestPair.endEdge) {
                let startX = (closestPair.startEdge.x - dropAreaRect.left) / scale;
                let startY = (closestPair.startEdge.y - dropAreaRect.top) / scale;
                let endX = (closestPair.endEdge.x - dropAreaRect.left) / scale;
                let endY = (closestPair.endEdge.y - dropAreaRect.top) / scale;

                // Ajustar la línea para que no se desplace fuera ni dentro del elemento
                const startElementStyles = window.getComputedStyle(connection.startElement);
                const endElementStyles = window.getComputedStyle(connection.endElement);

                // Ajuste de los bordes según el estilo del elemento
                const startAdjustmentX = (parseInt(startElementStyles.borderLeftWidth, 10) || 0) / scale;
                const startAdjustmentY = (parseInt(startElementStyles.borderTopWidth, 10) || 0) / scale;
                const endAdjustmentX = (parseInt(endElementStyles.borderLeftWidth, 10) || 0) / scale;
                const endAdjustmentY = (parseInt(endElementStyles.borderTopWidth, 10) || 0) / scale;

                startX += startAdjustmentX;
                startY += startAdjustmentY;
                endX += endAdjustmentX;
                endY += endAdjustmentY;

                // Actualizar la posición de la línea
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
      // Mostrar el contenedor de configuración
      if (this.configContainer) {
        this.configContainer.nativeElement.classList.add('show'); // Mostrar el contenedor
        
        // Lógica para cambiar el contenido del contenedor de configuración
        const configContent = this.configContainer.nativeElement.querySelector('.config-content');
        if (configContent) {
          // Dependiendo del tipo de elemento seleccionado, mostrar diferente contenido
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
                      // Manejador para mostrar/ocultar el input para el número
                      document.getElementById('rf-max-features').addEventListener('change', function() {
                          let maxFeaturesInput = document.getElementById('rf-max-features-number');
                          if (this.value === 'number') {
                              maxFeaturesInput.style.display = 'inline-block'; // Mostrar el campo de número
                          } else {
                              maxFeaturesInput.style.display = 'none'; // Ocultar el campo de número
                          }
                      });
            
                      // Asegura que el campo de número se muestre si "Number" está seleccionado inicialmente
                      window.addEventListener('load', function() {
                          let selectElement = document.getElementById('rf-max-features');
                          let numberInput = document.getElementById('rf-max-features-number');
                          if (selectElement.value === 'number') {
                              numberInput.style.display = 'inline-block';
                          } else {
                              numberInput.style.display = 'none'; // Asegura que el campo se oculte si no es "Number"
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
                    // Obtener los elementos del DOM
                    const kernelSelect = document.getElementById("svm-kernel");
                    const gammaInput = document.getElementById("svm-gamma");
                
                    // Agregar un evento para cambiar el estado de Gamma según el kernel seleccionado
                    kernelSelect.addEventListener('change', function() {
                        const selectedKernel = kernelSelect.value;
                
                        // Si se selecciona un kernel RBF o Polynomial, habilitar el campo de Gamma
                        if (selectedKernel === 'rbf' || selectedKernel === 'poly' || selectedKernel === 'sigmoid') {
                            gammaInput.disabled = false;
                        } else {
                            gammaInput.disabled = true;
                        }
                    });
                
                    // Inicializar el estado del formulario (si ya se ha seleccionado RBF o Polynomial por defecto)
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
    this.hideContextMenu();  // Ocultar el menú después de seleccionar una opción
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
      this.configContainer.nativeElement.classList.remove('show'); // Ocultar el contenedor
    }
  }
  
  hideContextMenu(): void {
    const menu = document.getElementById('context-menu');
    if (menu) {
      menu.style.display = 'none';  // Ocultar el menú
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
  
      // Establecer el origen de la transformación en la esquina superior izquierda
      dropArea.style.transformOrigin = 'top left';
      dropArea.style.transform = `scale(${this.zoomLevel})`;
  
      // Verificar el desbordamiento a la derecha
      if (dropAreaRect.right > containerRect.right) {
        const excessWidth = dropAreaRect.right - containerRect.right;
        dropArea.style.left = `-${excessWidth}px`;  // Desplazar hacia la izquierda
      } else {
        dropArea.style.left = '0px';  // Ajustar a la posición original
      }
  
      // Verificar el desbordamiento hacia abajo
      if (dropAreaRect.bottom > containerRect.bottom) {
        const excessHeight = dropAreaRect.bottom - containerRect.bottom;
        dropArea.style.top = `-${excessHeight}px`;  // Desplazar hacia arriba
      } else {
        dropArea.style.top = '0px';  // Ajustar a la posición original
      }
    }
  
    // Actualizar las posiciones de los elementos y las conexiones después de hacer zoom
    this.selectedElements.forEach((element) => {
      this.updateConnections(element);
    });
  }
  

  // Obtener el nivel de escala del área de trabajo
  private getZoomScale(): number {
    const dropArea = document.getElementById('drop-area');
    if (!dropArea) return 1; // Valor por defecto si no hay escala

    // Extraer el valor de 'scale' del estilo transform
    const transform = window.getComputedStyle(dropArea).transform;

    if (transform && transform !== 'none') {
        const match = transform.match(/matrix\((.+)\)/);
        if (match) {
            const values = match[1].split(',').map(parseFloat);
            return values[0]; // El primer valor de la matriz de transformación es la escala X
        }
    }

    return 1; // Si no hay transform, asumimos escala 1 (sin zoom)
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
      // Mostrar un prompt para pedir el nombre del escenario
      const name = window.prompt('Please enter the name of the scenario:');
    
      if (name) {
        // Si el usuario introduce un nombre, enviar la solicitud al backend
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
        // Si el usuario cancela o no introduce nada
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
        
        // Si design puede venir como string u objeto, verifica el tipo
        const designData = typeof this.scenario.design === 'string' 
          ? JSON.parse(this.scenario.design) 
          : this.scenario.design;
  
        // Ahora usa designData directamente
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
    
    // Confirmar si se desea guardar el diseño actual
    if (this.droppedElements.length > 0) {
      const confirmSave = confirm('Do you want to save the current scenario before loading the new scenario?');
      
      if (confirmSave === null) return; // Si el usuario cancela
      if (confirmSave) {
        await this.saveScenario(); // Esperar a que se complete el guardado
      }
    }

    // Limpiar diseño actual
    this.clearCurrentDesign();

    if (input?.files?.length) {
      const file = input.files[0];
      const reader = new FileReader();

      reader.onload = (e: ProgressEvent<FileReader>) => {
        try {
          const data = JSON.parse(e.target?.result as string);
          this.loadElementsFromJSON(data.elements);
          this.loadConnectionsFromJSON(data.connections || []); // <-- Cargar conexiones
        } catch (err) {
          alert('Error loading the scenario. Invalid format.');
        }
      };

      reader.readAsText(file);
    }
    
    // Resetear el input de archivo
    input.value = '';
  }

  private clearCurrentDesign(): void {
    // 1. Eliminar elementos del DOM de forma explícita
    const container = document.getElementById('content-container');
    
    if (container) {
      // Método más confiable para eliminar elementos
      while (container.firstChild) {
        container.removeChild(container.firstChild);
      }
  
      // Alternativa adicional para SVG y elementos residuales
      const svgElements = container.getElementsByTagName('svg');
      while (svgElements.length > 0) {
        svgElements[0].parentNode?.removeChild(svgElements[0]);
      }
    }
  
    // 2. Limpiar las referencias de los elementos
    this.droppedElements.forEach(element => {
      if (element.parentElement) {
        element.parentElement.removeChild(element);
      }
    });
  
    // 3. Reiniciar los arrays
    this.droppedElements = [];
    this.selectedElements = [];
  
    // 4. Eliminar conexiones del SVG
    this.connections.forEach(connection => {
      if (connection.line.parentElement) {
        connection.line.parentElement.removeChild(connection.line);
      }
    });
    this.connections = [];
  
    // 5. Forzar actualización del renderizado
    setTimeout(() => {
      if (container) {
        // Truco para forzar reflow
        void container.offsetHeight;
        
        // Actualizar estilos
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
      newElement.id = element.id; // <-- Restaurar ID
      
      // Actualizar nextElementId
      const match = element.id.match(/element-(\d+)/);
      if (match) {
        const idNum = parseInt(match[1], 10);
        if (idNum > maxId) maxId = idNum;
      }
      
      // Configurar posición
      newElement.style.position = 'absolute';
      newElement.style.left = `${element.position.left}px`;
      newElement.style.top = `${element.position.top}px`;

      // Agregar eventos e íconos
      this.setupElementEvents(newElement);
      this.addControlIcons(newElement);

      // Añadir al workspace
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

    // Configurar eventos de hover
    element.addEventListener('mouseenter', () => {
      gearIcon.style.display = 'block';
      arrowIcon.style.display = 'block';
    });

    element.addEventListener('mouseleave', () => {
      gearIcon.style.display = 'none';
      arrowIcon.style.display = 'none';
    });

    // Configurar eventos de clic
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
    newElement.setAttribute('data-type', type); // Añadir esta línea
  
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
      case 'PCA': return 'fa fa-cogs'; // PCA icon (same as a general settings icon)
      case 'Normalizer': return 'fa fa-adjust'; // Adjust icon for Normalizer
      case 'KNNImputer': return 'fa fa-users'; // KNN Imputer icon (same as KNN)
      case 'CNN': return 'fa fa-brain';
      case 'RNN': return 'fa fa-sync-alt';
      case 'KNN': return 'fa fa-users';
      case 'RandomForest': return 'fa fa-tree';
      case 'LogisticRegression': return 'fa fa-chart-line';
      case 'SVM': return 'fa fa-vector-square';
      case 'GradientBoosting': return 'fa fa-fire';
      case 'DecisionTree': return 'fa fa-tree'; // Decision Tree icon (same as Random Forest)
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
