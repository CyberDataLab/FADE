import { Component, OnInit, Inject, Injector, ViewChild, ElementRef, AfterViewInit, NgModule } from '@angular/core';
import { PLATFORM_ID, Renderer2 } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { ScenarioService } from '../../scenario.service';
import { Scenario } from '../../../DTOs/Scenario';
import { HttpClient } from '@angular/common/http';
import { NodeEditor, GetSchemes, ClassicPreset } from 'rete';
import { AngularPlugin, AngularArea2D, Presets } from 'rete-angular-plugin';
import { ConnectionPlugin, Presets as ConnectionPresets } from 'rete-connection-plugin';
import { AreaPlugin, AreaExtensions } from 'rete-area-plugin';
import { createEditor } from './editor';
import e from 'express';
import { ToolbarService } from './toolbar.service';
import { Subscription } from 'rxjs';


type Schemes = GetSchemes<
  ClassicPreset.Node,
  ClassicPreset.Connection<ClassicPreset.Node, ClassicPreset.Node>
>;
type AreaExtra = AngularArea2D<Schemes>;

@Component({
    selector: 'app-new-scenario',
    imports: [
        CommonModule
    ],
    templateUrl: './new-scenario.component.html',
    styleUrl: './new-scenario.component.css'
})

export class NewScenarioComponent implements OnInit, AfterViewInit{
  config: any = {};

  //RETEJS

  editorRef!: {
    editor: NodeEditor<Schemes>;
    area: AreaPlugin<Schemes, AreaExtra>;
    addElement: (type: string, position: [number, number], displayName?: string, icon?: string, id?: string) => Promise<void>;
    getNodeType: (nodeId: string) => Promise<string | undefined>;
    connectNodesById: (connections: { startId: string; startOutput: string; endId: string; endInput: string }[]) => Promise<void>;
    clearEditor: () => void;
    destroy: () => void;
  };

  draggedNodeType: string | null = null;
  
  showConfigContainer = false;

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

  isNewScenario: boolean = true;

  scenarioId: string | null = null;

  selectedCSVFiles: File[] = [];
  selectedNetworkFiles: File[] = [];

  private elementParameters: { [elementId: string]: any } = {};
  private currentCSVElementId: string | null = null;
  private currentNetworkElementId: string | null = null;

  private saveSub: Subscription | null = null;

  constructor(@Inject(PLATFORM_ID) private platformId: Object, private injector: Injector, private scenarioService: ScenarioService, private route: ActivatedRoute, private renderer: Renderer2, private http: HttpClient, private toolbarService: ToolbarService) {}

  @ViewChild('configContainer', { static: true }) configContainer!: ElementRef;
  @ViewChild('dropArea', { static: true }) reteContainer!: ElementRef;

  ngOnInit() {
    if (isPlatformBrowser(this.platformId)) {
      document.addEventListener('wheel', (e) => {
        e.preventDefault();
      }, { passive: false });

      const saveScenario = document.getElementById('saveScenario');
      if (saveScenario) {
        saveScenario.addEventListener('click', () => this.saveScenario());
      }

      this.scenarioService.saveRequested$.subscribe(() => this.saveScenario());
      
      this.scenarioId = this.route.snapshot.paramMap.get('id');

      if (this.scenarioId) {
        this.isNewScenario = false;
        this.loadEditScenario(this.scenarioId);
      } 

      this.loadSections();

      this.toolbarService.showSaveButton();
      this.saveSub = this.toolbarService.saveRequested$.subscribe(() => {
        this.saveScenario();
      });
    }
  }

  ngOnDestroy(): void {
    this.toolbarService.hideSaveButton();
    this.saveSub?.unsubscribe();
  }

  async ngAfterViewInit() {
    if (isPlatformBrowser(this.platformId)) {
      const container = this.reteContainer.nativeElement;
  
      this.editorRef = await createEditor(
        container,
        this.injector,
        (node) => this.openConfigForNode(node),
        (node) => this.deleteNode(node)
      );
    }
  }

  async deleteNode(node: ClassicPreset.Node) {
    if (!node) return;
  
    delete this.elementParameters[node.id];
  }

  openConfigForNode(node: ClassicPreset.Node) {
    if (!node) return;
  
    const configContainerEl = this.configContainer?.nativeElement;
    if (!configContainerEl) return;
  
    configContainerEl.classList.add('show');
  
    const configContent = configContainerEl.querySelector('.config-content') as HTMLElement;
    if (!configContent) return;
    configContent.innerHTML = '';
  
    const elementType = (node as any).data.type;
    if (!elementType) return;
      
    if (elementType === 'CSV') {
      this.handleCSVConfiguration(node, configContent);
      return;
    }

    if (elementType === 'Network') {
      this.handleNetworkConfiguration(node, configContent);
      return;
    }

    if (elementType === 'ClassificationMonitor') {
      this.handleClassificationMonitorConfiguration(node, configContent);
      return;
    }

    if (elementType === 'RegressionMonitor') {
      this.handleRegressionMonitorConfiguration(node, configContent);
      return;
    }
    
    const elementConfig = this.getElementConfig(elementType);
    if (!elementConfig) return;
  
    configContent.innerHTML = this.generateConfigHTML(elementConfig, node.id);
    this.setupDynamicInputs(node, elementConfig);
  
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
  
    // 🔽 Inicializar parámetros por defecto ANTES de renderizar
    if (!this.elementParameters[elementId]) {
      this.elementParameters[elementId] = {};
      config.properties.forEach((prop: any) => {
        if (!prop.conditional) {
          this.elementParameters[elementId][prop.name] = prop.default;
        } else {
          const parentValue = this.elementParameters[elementId][prop.conditional.dependsOn];
          if (parentValue === prop.conditional.value) {
            this.elementParameters[elementId][prop.name] = prop.default;
          }
        }
      });
    }
  
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

        case 'textarea':
          html += `
            <div style="display: flex; flex-direction: column; margin-bottom: 60px;">
              <label for="${prop.name}-${elementId}" style="margin-bottom: 10px;">
                ${this.formatPropertyName(prop.label)}:
              </label>

              <div style="display: flex; justify-content: flex-end; gap: 5px; margin-bottom: 5px;">
                <button id="zoom-in-${elementId}-${prop.name}" type="button"
                  style="
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 20px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    color: white;
                  "
                  onmouseover="this.style.borderColor='#fff';"
                  onmouseout="this.style.borderColor='transparent';"
                >🔍+</button>
                
                <button id="zoom-out-${elementId}-${prop.name}" type="button"
                  style="
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 20px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    color: white;
                  "
                  onmouseover="this.style.borderColor='#fff';"
                  onmouseout="this.style.borderColor='transparent';"
                >🔍−</button>
              </div>

              <textarea 
                id="${prop.name}-${elementId}"
                placeholder="${prop.placeholder || ''}"
                style="width: 100%; min-height: 200px; padding: 10px; font-family: monospace; font-size: 10px; border: 1px solid #ccc; border-radius: 4px; resize: vertical; overflor-y: auto;"
              >${formattedValue}</textarea>
            </div>`;
          break;
        case 'repeat-group': {
          const containerId = `${prop.name}-container-${elementId}`;
          html += `<div id="${containerId}">`;
        
          const repeatCount = this.elementParameters[elementId]?.[prop.repeat] || prop.default || 1;
          for (let i = 0; i < repeatCount; i++) {
            html += `<fieldset style="border: 1px solid #ccc; padding: 10px; margin-bottom: 10px;">
                      <legend>${prop.label} #${i + 1}</legend>`;
            for (const subProp of prop.template) {
              const subPropClone = { ...subProp, name: `${prop.name}_${i}_${subProp.name}` };
              html += this.generatePropertyHTML(subPropClone, elementId);
            }
            html += `</fieldset>`;
          }
        
          html += `</div>`;
          break;
      }
    }

    return html;
  }

  private evaluateInitialConditionalVisibility(config: any, elementId: string): void {
    config.properties.forEach((prop: any) => {
      if (prop.conditional) {
        const dependsOn = prop.conditional.dependsOn;
        const dependsValue = prop.conditional.value;
  
        // Detectar si estamos en un repeat-group por el nombre
        const repeatMatch = prop.name.match(/^(.+?)_(\d+)_/);
        let resolvedDependsOn = dependsOn;
  
        if (repeatMatch) {
          const prefix = repeatMatch[1];
          const index = repeatMatch[2];
          resolvedDependsOn = `${prefix}_${index}_${dependsOn}`;
        }
  
        const controllingValue = this.elementParameters[elementId]?.[resolvedDependsOn];
        const dependentRow = document.getElementById(`${prop.name}-row-${elementId}`);
  
        if (dependentRow) {
          const shouldShow = controllingValue === dependsValue;
          dependentRow.style.display = shouldShow ? 'grid' : 'none';
        }
      }
    });
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
  
  private setupDynamicInputs(node: ClassicPreset.Node, config: any): void {
    const elementId = node.id;

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
                .filter((p: any) => {
                  const regex = /^(.+?)_(\d+)_/;
                  const match = paramKey.match(regex);
                  if (match) {
                    // Estamos en un repeat-group
                    const prefix = match[1];
                    const index = match[2];
                    const expectedControlName = `${prefix}_${index}_${p.conditional?.dependsOn}`;
                    return p.conditional && expectedControlName === paramKey;
                  } else {
                    return p.conditional && p.conditional.dependsOn === paramKey;
                  }
                })
                .forEach((dependentProp: any) => {
                  const regex = /^(.+?)_(\d+)_/;
                  const match = paramKey.match(regex);
                  let dependentName = dependentProp.name;
        
                  if (match) {
                    const prefix = match[1];
                    const index = match[2];
                    dependentName = `${prefix}_${index}_${dependentProp.name}`;
                  }
        
                  const dependentRow = document.getElementById(`${dependentName}-row-${elementId}`);
        
                  if (dependentRow) {
                    const isVisible = newValue === dependentProp.conditional.value;
                    dependentRow.style.display = isVisible ? 'grid' : 'none';
        
                    if (isVisible) {
                      if (!(dependentName in this.elementParameters[elementId])) {
                        this.elementParameters[elementId][dependentName] = dependentProp.default;
                      }
        
                      // Forzar valor por defecto
                      setTimeout(() => {
                        const input = document.getElementById(`${dependentName}-${elementId}`) as HTMLInputElement;
                        if (input && dependentProp.default !== undefined) {
                          input.value = dependentProp.default.toString();
                        }
                      }, 0);
                    } else {
                      delete this.elementParameters[elementId][dependentName];
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
              const newValue = parseInt(input.value, 10);
              this.elementParameters[elementId][paramKey] = newValue;
        
              // Verifica si este número controla un repeat-group
              const affectedRepeatGroups = config.properties.filter((p: any) => 
                p.type === 'repeat-group' && p.repeat === paramKey
              );
        
              affectedRepeatGroups.forEach((repeatProp: any) => {
                const containerId = `${repeatProp.name}-container-${elementId}`;
                const container = document.getElementById(containerId);
                if (container) {
                  container.innerHTML = '';
        
                  for (let i = 0; i < newValue; i++) {
                    const fieldset = document.createElement('fieldset');
                    fieldset.style.border = '1px solid #ccc';
                    fieldset.style.padding = '10px';
                    fieldset.style.marginBottom = '10px';
        
                    const legend = document.createElement('legend');
                    legend.textContent = `${repeatProp.label} #${i + 1}`;
                    fieldset.appendChild(legend);
        
                    for (const subProp of repeatProp.template) {
                      const subPropClone = { ...subProp, name: `${repeatProp.name}_${i}_${subProp.name}` };
                      const html = this.generatePropertyHTML(subPropClone, elementId);
                      const tempDiv = document.createElement('div');
                      tempDiv.innerHTML = html;
                      Array.from(tempDiv.children).forEach(child => fieldset.appendChild(child));
                    }
        
                    container.appendChild(fieldset);
                  }
        
                  // Reaplicar listeners de inputs recién creados
                  this.setupDynamicInputs({ id: elementId } as any, { properties: repeatProp.template.map((sp: any) => ({
                    ...sp,
                    name: `${repeatProp.name}_${0}_${sp.name}`
                  })) });
                }
              });
            });
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

        case 'textarea': {
          const textarea = document.getElementById(controlId) as HTMLTextAreaElement;
        
          if (textarea) {
            textarea.value = this.elementParameters[elementId][paramKey] || '';
        
            textarea.addEventListener('input', () => {
              this.elementParameters[elementId][paramKey] = textarea.value;
            });

            textarea.addEventListener('wheel', (e) => {
              const scrollTop = textarea.scrollTop;
              const scrollHeight = textarea.scrollHeight;
              const clientHeight = textarea.clientHeight;
            
              const isScrollingDown = e.deltaY > 0;
              const isScrollingUp = e.deltaY < 0;
            
              const atTop = scrollTop === 0;
              const atBottom = scrollTop + clientHeight >= scrollHeight - 1;
            
              const shouldStop = 
                (isScrollingUp && !atTop) ||
                (isScrollingDown && !atBottom);
            
              if (shouldStop) {
                e.stopPropagation();
              }
            });
            
            const zoomIn = document.getElementById(`zoom-in-${elementId}-${paramKey}`);
            const zoomOut = document.getElementById(`zoom-out-${elementId}-${paramKey}`);
        
            const maxFontSize = 13;  
            const minFontSize = 7; 

            const updateFontSize = (delta: number) => {
              const currentSize = parseFloat(window.getComputedStyle(textarea).fontSize);
              const newSize = Math.max(minFontSize, Math.min(maxFontSize, currentSize + delta));
              textarea.style.fontSize = `${newSize}px`;
            };
        
            zoomIn?.addEventListener('click', () => updateFontSize(1));
            zoomOut?.addEventListener('click', () => updateFontSize(-1));
          }
          break;
        }
        case 'repeat-group': {
          const repeatCount = this.elementParameters[elementId]?.[prop.repeat] || prop.default || 1;

          for (let i = 0; i < repeatCount; i++) {
            for (const subProp of prop.template) {
              const subPropName = `${prop.name}_${i}_${subProp.name}`;
              const subControlId = `${subPropName}-${elementId}`;
              const input = document.getElementById(subControlId) as HTMLInputElement | HTMLSelectElement;

              if (input) {
                if (!(subPropName in this.elementParameters[elementId])) {
                  this.elementParameters[elementId][subPropName] = subProp.default;
                }

                // Establecer el valor inicial
                input.value = this.elementParameters[elementId][subPropName] || subProp.default;

                // Escuchar cambios
                input.addEventListener('input', () => {
                  this.elementParameters[elementId][subPropName] = input.value;
                });
              }
            }
          }
          break;
        }     
      }
    });
    this.evaluateInitialConditionalVisibility(config, node.id);

  }

  private handleCSVConfiguration(node: ClassicPreset.Node, configContent: HTMLElement): void {
    configContent.innerHTML = `<h3>CSV file configuration</h3><p>Please select a CSV file:</p> <div id="csv-columns-selection"></div>`;
    
    const input = this.createFileInput('csv-upload', '.csv', (e) => this.onCSVFileSelected(e));
    const fileNameElement = this.createFileNameElement();
    
    configContent.appendChild(input);
    configContent.appendChild(fileNameElement);
    
    this.currentCSVElementId = node.id;
    if (this.elementParameters[node.id]?.columns) {
      this.updateCSVColumnSelectionUI(
        Object.keys(this.elementParameters[node.id].columns), 
        node.id
      );
    }
  }

  private handleNetworkConfiguration(node: ClassicPreset.Node, configContent: HTMLElement): void {
    configContent.innerHTML = `<h3>Network file configuration</h3><p>Please select a PCAP file:</p>`;
    
    const input = this.createFileInput('network-upload', '.pcap', (e) => this.onNetworkFileSelected(e));
    const fileNameElement = this.createFileNameElement();
    
    configContent.appendChild(input);
    configContent.appendChild(fileNameElement);
    
    this.currentNetworkElementId = node.id;
  }
  
  private handleClassificationMonitorConfiguration(node: ClassicPreset.Node, configContent: HTMLElement): void {
    configContent.innerHTML = `<h3>Classification Monitor Configuration</h3><p>Select metrics to monitor:</p><div id="metrics-selection"></div>`;
    const metrics = ['f1Score', 'accuracy', 'recall', 'precision', 'confusionMatrix'];
    this.updateClassificationMetricsSelectionUI(metrics, node.id);
  }

  private handleRegressionMonitorConfiguration(node: ClassicPreset.Node, configContent: HTMLElement): void {
    configContent.innerHTML = `<h3>Regression Monitor Configuration</h3><p>Select metrics to monitor:</p><div id="metrics-selection"></div>`;
    const metrics = ['mse', 'rmse', 'mae', 'r2', 'msle'];
    this.updateRegressionMetricsSelectionUI(metrics, node.id);
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
        const file = input.files[0];

        // Evita duplicados por nombre (opcional)
        const alreadyExists = this.selectedCSVFiles.some(f => f.name === file.name);
        if (!alreadyExists) {
          this.selectedCSVFiles.push(file);
        }
        
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

  onNetworkFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input && input.files) {
      const file = input.files[0];
      if (file && file.name.endsWith('.pcap')) {
        const file = input.files[0];

        // Evita duplicados por nombre (opcional)
        const alreadyExists = this.selectedNetworkFiles.some(f => f.name === file.name);
        if (!alreadyExists) {
          this.selectedNetworkFiles.push(file);
        }
        
        const reader = new FileReader();
        reader.onload = (e: any) => {
          const text = e.target.result;
          const rows = text.split('\n');
          if (rows.length < 1) return;
          
          const columns = rows[0].split(',').map((col: string) => col.trim().replace(/^"|"$/g, ''));
  
          const elementId = this.currentNetworkElementId;
          if (!elementId) return;
          
          this.elementParameters[elementId] = {
            networkFileName: file.name
          };
        };
        reader.readAsText(file);
      }
    }
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

  onDragStart(event: DragEvent, isWorkspace: boolean): void {
    const target = event.target as HTMLElement;
    this.draggedNodeType = target.getAttribute('data-type');

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
  
  async onDrop(event: DragEvent) {
    event.preventDefault();
    const [dropX, dropY] = this.getDropCoordinates(event);

    const nodeInfo = this.findElementInfoByType(this.draggedNodeType!);

    if (!nodeInfo) {
      console.error('Elemento no encontrado en config.json para tipo:', this.draggedNodeType);
      return;
    }

    const { displayName, icon } = nodeInfo;
  
    this.editorRef.addElement(this.draggedNodeType!, [dropX, dropY], displayName, icon, );
  }

  getDropCoordinates(event: DragEvent): [number, number] {
    const rect = this.reteContainer.nativeElement.getBoundingClientRect();
  
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
  
    const transform = this.editorRef.area.area.transform;
  
    const transformedX = (x - transform.x) / transform.k;
    const transformedY = (y - transform.y) / transform.k;
  
    return [transformedX, transformedY];
  }

  findElementInfoByType(type: string): { displayName: string, icon: string } | null {
    const sections = this.config.sections;
    for (const sectionKey in sections) {
      const section = sections[sectionKey];
      const categories = Array.isArray(section) ? section : Object.values(section);
      for (const category of categories) {
        if (!Array.isArray(category)) continue;
        for (const element of category) {
          if (element.type === type) {
            return {
              displayName: element.displayName,
              icon: element.icon
            };
          }
        }
      }
    }
    return null;
  }

  async getCurrentDesign(): Promise<any> {
    const nodes = this.editorRef.editor.getNodes();
  
    const savedElements = await Promise.all(nodes.map(async (node) => {
      const elementParams = this.elementParameters[node.id] || {};
      const type = await this.editorRef.getNodeType(node.id);
  
      if (type === 'CSV' && elementParams.columns) {
        elementParams.columns = elementParams.columns.map((col: any) => ({
          name: col.name,
          selected: col.selected
        }));
      }
  
      const nodeView = this.editorRef.area.nodeViews.get(node.id);
      const position = nodeView?.position;
  
      if (!position) {
        throw new Error(`No se pudo obtener la posición del nodo con ID: ${node.id}`);
      }
  
      return {
        id: node.id,
        type,
        position: {
          left: position['x'],
          top: position['y'],
        },
        parameters: elementParams
      };
    }));
  
    const connections = this.editorRef.editor.getConnections();
  
    const savedConnections = connections.map((conn: any) => ({
      startId: conn.source,
      startOutput: conn.sourceOutput,
      endId: conn.target,
      endInput: conn.targetInput
    }));
  
    return {
      elements: savedElements,
      connections: savedConnections,
    };
  }
  

  async saveScenario(): Promise<void> {
    const design = await this.getCurrentDesign();
  
    if (this.isNewScenario) {
      const name = window.prompt('Please enter the name of the scenario:');
  
      if (name) {
        this.scenarioService.saveScenario(
          name,
          design,
          this.selectedCSVFiles || [],
          this.selectedNetworkFiles || []
        ).subscribe({
          next: (response: any) => {
            alert('Scenario saved correctly.');
            this.scenarioId = response.uuid;
            this.isNewScenario = false;
            this.scenarioService.setUnsavedChanges(false);
          },
          error: (error: any) => {
            const errorMsg = error?.error?.error || 'Unexpected error';
            alert('Error creating scenario: ' + JSON.stringify(errorMsg));
          }
        });
      } else {
        alert('Error while saving the scenario, you must provide a name.');
      }
  
    } else {
      if (this.scenarioId != null) {
        this.scenarioService.editScenario(
          this.scenarioId,
          design,
          this.selectedCSVFiles || [],
          this.selectedNetworkFiles || []
        ).subscribe({
          next: () => {
            alert('Scenario updated correctly.');
            this.scenarioService.setUnsavedChanges(false);
          },
          error: (error: any) => {
            const errorMsg = error?.error?.error || 'Unexpected error';
            alert('Error editing scenario: ' + JSON.stringify(errorMsg));
          }
        });
      }
    }
  }

  async loadEditScenario(uuid: string): Promise<void> {
    this.scenarioService.getScenarioById(uuid).subscribe(
      async (response: Scenario) => {
        this.scenario = response;
        
        const designData = typeof this.scenario.design === 'string' 
          ? JSON.parse(this.scenario.design) 
          : this.scenario.design;
  
        await this.editorRef.clearEditor(); // 💥 Limpieza previa
        await this.loadElementsFromJSON(designData.elements);
        await this.loadConnectionsFromJSON(designData.connections || []);
      },
      (error: any) => {
        console.error('Error getting scenario:', error);
        const errorMsg = error?.error?.error || 'Unexpected error';
        alert('Error loading scenario: ' + JSON.stringify(errorMsg));
      }
    );
  }

  private async loadElementsFromJSON(savedElements: any[]): Promise<void> {
    savedElements.forEach(async (element: any) => {
      const nodeInfo = this.findElementInfoByType(element.type);

      if (!nodeInfo) {
        console.error('Elemento no encontrado en config.json para tipo:', this.draggedNodeType);
        return;
      }
    
      const { displayName, icon } = nodeInfo;
    
      await this.editorRef.addElement(element.type, [element.position.left, element.position.top], displayName, icon, element.id);
      
      if (element.type === 'CSV' && element.parameters?.columns) {
        this.elementParameters[element.id] = {
          ...element.parameters,
          columns: element.parameters.columns 
        };
      }
      else {
        this.elementParameters[element.id] = element.parameters;
      }
    });
    this.updateUnsavedState();
  }

  private async loadConnectionsFromJSON(savedConnections: any[]): Promise<void> {
    await this.editorRef.connectNodesById(savedConnections);
  }
}
