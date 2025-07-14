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

  editorRef!: {
    editor: NodeEditor<Schemes>;
    area: AreaPlugin<Schemes, AreaExtra>;
    addElement: (type: string, position: [number, number], displayName?: string, icon?: string, id?: string) => Promise<ClassicPreset.Node>;
    getNodeType: (nodeId: string) => Promise<string | undefined>;
    connectNodesById: (connections: { startId: string; startOutput: string; endId: string; endInput: string }[]) => Promise<void>;
    clearEditor: () => void;
    destroy: () => void;
  };

  draggedNodeType: string | null = null;
  
  showConfigContainer = false;

  activeSections: { [key: string]: boolean } = {};

  activeSubSections: { [key in 'classification' | 'regression' | 'anomalyDetection' | 'explainability' | 'monitoring']: boolean } = {
    classification: false,
    regression: false,
    anomalyDetection: false,
    explainability: false,
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
  
    if (elementType === 'ClassificationMonitor') {
      this.handleClassificationMonitorConfiguration(node, configContent);
      return;
    }
  
    if (elementType === 'RegressionMonitor') {
      this.handleRegressionMonitorConfiguration(node, configContent);
      return;
    }
  
    if (elementType === 'SHAP') {
      const shapId = node.id;
    
      const findClassesFromUpstream = (nodeId: string): string[] | null => {
        const connections = Array.from(this.editorRef.editor.getConnections()) as Array<ClassicPreset.Connection<ClassicPreset.Node, ClassicPreset.Node>>;
        const incoming = connections.filter(c => c.target === nodeId);
    
        for (const conn of incoming) {
          const sourceId = conn.source;
          const sourceParams = this.elementParameters[sourceId];
          const sourceType = (this.editorRef.editor.getNode(sourceId) as any)?.data?.type;
    
          const isAnomalyModel = this.config?.sections?.dataModel?.anomalyDetection?.some(
            (e: any) => e.type === sourceType
          );
    
          if (isAnomalyModel) {
            return ['normal', 'anomaly'];
          }
    
          if (sourceParams?.classes?.length) {
            const originalClasses = sourceParams.classes;
            if (typeof originalClasses[0] === 'string') {
              return originalClasses.map((cls: string) => ({ name: cls, selected: true }));
            }
            return originalClasses;
          }
    
          const fromParent = findClassesFromUpstream(sourceId);
          if (fromParent) return fromParent;
        }
        return null;
      };
    
      const foundClasses = findClassesFromUpstream(shapId);
      if (foundClasses?.length) {
        this.elementParameters[shapId] = {
          ...this.elementParameters[shapId],
          classes: foundClasses
        };
      }
    
      const elementConfig = this.getElementConfig(elementType);
      if (!elementConfig) return;
    
      configContent.innerHTML = this.generateConfigHTML(elementConfig, node.id);
      this.setupDynamicInputs(node, elementConfig);
      this.hideContextMenu();
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
      if (obj.explainability) {
        const found = obj.explainability.find((e: any) => e.type === elementType);
        if (found) return found;
      }
      if (obj.anomalyDetection) {
        const found = obj.anomalyDetection.find((e: any) => e.type === elementType);
        if (found) return found;
      }

      if (obj.monitoring) {
        const found = obj.monitoring.find((e: any) => e.type === elementType);
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
  
    if (!this.elementParameters[elementId]) {
      this.elementParameters[elementId] = {};
    }
    
    config.properties.forEach((prop: any) => {
      if (prop.conditional) {
        const parentValue = this.elementParameters[elementId][prop.conditional.dependsOn];
        if (parentValue === prop.conditional.value && !(prop.name in this.elementParameters[elementId])) {
          this.elementParameters[elementId][prop.name] = prop.default;
        }
      } else if (!(prop.name in this.elementParameters[elementId])) {
        this.elementParameters[elementId][prop.name] = prop.default;
      }
    });
    
  
    if (!config.properties || !Array.isArray(config.properties)) {
      console.error(`Configuración inválida para ${config.type}`);
      return html + '<p>Error de configuración</p>';
    }
  
    config.properties.forEach((prop: any) => {
      if (!prop.name || !prop.type) {
        console.warn(`Propiedad inválida en ${config.type}:`, prop);
        return;
      }
  
      if (prop.type === 'conditional-repeat-group-by-index') {
        html += `<div id="${prop.name}-container-${elementId}"></div>`;
      } else {
        html += this.generatePropertyHTML(prop, elementId);
      }
    });
  
    return html;
  }
  
  
  
  private generatePropertyHTML(prop: any, elementId: string): string {
    let html = '';
    let currentValue: any = undefined;

    if (prop.groupName !== undefined && prop.repeatIndex !== undefined) {
      const originalName = prop.name.replace(`${prop.groupName}_${prop.repeatIndex}_`, '');
      const group = this.elementParameters[elementId]?.[prop.groupName] || [];
      currentValue = group[prop.repeatIndex]?.[originalName] ?? prop.default;
    } else {
      currentValue = this.elementParameters[elementId]?.[prop.name] ?? prop.default;
    }


    const formattedValue = currentValue !== undefined ? currentValue.toString() : prop.default;

    switch (prop.type) {
      case 'file':
        html += `
          <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
            <label for="${prop.name}-${elementId}">${this.formatPropertyName(prop.label || prop.name)}:</label>
            <input type="file" id="${prop.name}-${elementId}" accept="${prop.accept || '*'}" />
          </div>`;
        break;

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

      case 'select': {
        const hasConditional = prop.conditional !== undefined;
        const initialDisplay = hasConditional ? 'none' : 'grid';
        const divId = `${prop.name}-row-${elementId}`;
      
        html += `
          <div id="${divId}" style="display: ${initialDisplay}; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
            <label for="${prop.name}-${elementId}" style="text-align: left;">${this.formatPropertyName(prop.label)}:</label>
            <select id="${prop.name}-${elementId}" style="height: 30px; padding: 3px 5px; vertical-align: middle; line-height: 20px; margin-top: -10px;">
              ${prop.options.map((opt: string) => `
                <option value="${opt}" ${formattedValue === opt ? 'selected' : ''}>
                  ${this.formatOptionName(opt)}
                </option>`
              ).join('')}
            </select>
          </div>`;
        break;
      }
        
        
      case 'dynamic-select':
        html += `
          <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
            <label for="${prop.name}-${elementId}" style="flex: 1;">${this.formatPropertyName(prop.label)}:</label>
            <select id="${prop.name}-${elementId}" style="height: 3.6em; padding: 0.75em 1em; font-size: 16px; line-height: 1.2; flex: 2; box-sizing: border-box;">
              <!-- Opciones generadas dinámicamente en setupDynamicInputs -->
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

        case 'multi-select': 
          html += `
            <div id="${prop.name}-row-${elementId}" style="margin-bottom: 60px;">
              <label style="text-align: left; display: block; margin-bottom: 10px;">
                ${this.formatPropertyName(prop.label)}:
              </label>
              <div id="${prop.name}-container-${elementId}" class="csv-columns-container"></div>
            </div>`;
          break;   
    }

    return html;
  }

  private evaluateInitialConditionalVisibility(config: any, elementId: string): void {
    config.properties.forEach((prop: any) => {
      if (!prop.conditional) return;
  
      const rowId = `${prop.name}-row-${elementId}`;
      const dependentRow = document.getElementById(rowId);
      if (!dependentRow) return;
  
      const isInGroup = prop.groupName !== undefined && prop.repeatIndex !== undefined;
      let controllingValue;
  
      if (isInGroup) {
        const originalName = prop.conditional.dependsOn;
        controllingValue = this.elementParameters[elementId]?.[prop.groupName]?.[prop.repeatIndex]?.[originalName];
      } else {
        controllingValue = this.elementParameters[elementId]?.[prop.conditional.dependsOn];
      }
  
      const shouldShow = controllingValue === prop.conditional.value;
      dependentRow.style.display = shouldShow ? 'grid' : 'none';
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
      const isInGroup = prop.groupName !== undefined && prop.repeatIndex !== undefined;
  
      const getCurrentValue = (): any => {
        if (isInGroup) {
          const originalName = paramKey.replace(`${prop.groupName}_${prop.repeatIndex}_`, '');
          return this.elementParameters[elementId][prop.groupName]?.[prop.repeatIndex]?.[originalName];
        } else {
          return this.elementParameters[elementId][paramKey];
        }
      };
  
      const saveValue = (value: any) => {
        if (isInGroup) {
          const originalName = paramKey.replace(`${prop.groupName}_${prop.repeatIndex}_`, '');
          this.elementParameters[elementId][prop.groupName][prop.repeatIndex][originalName] = value;
        } else {
          this.elementParameters[elementId][paramKey] = value;
        }
      };
  
      const deleteValue = () => {
        if (isInGroup) {
          const originalName = paramKey.replace(`${prop.groupName}_${prop.repeatIndex}_`, '');
          delete this.elementParameters[elementId][prop.groupName][prop.repeatIndex][originalName];
        } else {
          delete this.elementParameters[elementId][paramKey];
        }
      };

      const propKeyWithoutPrefix = (key: string, index: number) => key.replace(`conv_layers_${index}_`, '');

  
      switch (prop.type) {
        case 'file': {
          const fileInput = document.getElementById(controlId) as HTMLInputElement;
          if (fileInput) {
            fileInput.addEventListener('change', (event: Event) => {
              const input = event.target as HTMLInputElement;
              if (input.files?.length) {
                const file = input.files[0];
                if (prop.name === 'networkFileName') {
                  this.onNetworkFileSelected(event);
                }
                saveValue(file.name);
              }
            });
          }
          this.currentNetworkElementId = node.id;
          break;
        }
        
        case 'conditional-select': {
          const selectId = `${paramKey}-select-${elementId}`;
          const select = document.getElementById(selectId) as HTMLSelectElement;
        
          if (select) {
            select.value = getCurrentValue() ?? prop.default;
        
            select.addEventListener('change', () => {
              const newValue = select.value;
              this.saveCurrentConvLayerParams(elementId, config);
              saveValue(newValue);
              this.renderSelectedConvLayerConfig(elementId, config);
        
              if (isInGroup) {
                const controllingKey = paramKey.replace(`${prop.groupName}_${prop.repeatIndex}_`, '');
        
                config.properties
                  .filter((p: any) =>
                    p.groupName === prop.groupName &&
                    p.repeatIndex === prop.repeatIndex &&
                    p.conditional?.dependsOn === controllingKey
                  )
                  .forEach((dependentProp: any) => {
                    const rowId = `${dependentProp.name}-row-${elementId}`;
                    const dependentRow = document.getElementById(rowId);
        
                    const shouldShow = newValue === dependentProp.conditional.value;
        
                    if (dependentRow) {
                      dependentRow.style.display = shouldShow ? 'grid' : 'none';
                    }
        
                    const originalName = dependentProp.name.replace(`${prop.groupName}_${prop.repeatIndex}_`, '');
        
                    if (shouldShow) {
                      this.elementParameters[elementId][prop.groupName][prop.repeatIndex][originalName] = dependentProp.default;
                      const inputEl = document.getElementById(`${dependentProp.name}-${elementId}`) as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
                      if (inputEl) inputEl.value = dependentProp.default;
                    } else {
                      delete this.elementParameters[elementId][prop.groupName][prop.repeatIndex][originalName];
                    }
                  });
        
              } else {
                config.properties
                  .filter((p: any) => p.conditional?.dependsOn === paramKey)
                  .forEach((dependentProp: any) => {
                    const rowId = `${dependentProp.name}-row-${elementId}`;
                    const dependentRow = document.getElementById(rowId);
        
                    const shouldShow = newValue === dependentProp.conditional.value;
        
                    if (dependentRow) {
                      dependentRow.style.display = shouldShow ? 'grid' : 'none';
                    }
        
                    if (shouldShow) {
                      this.elementParameters[elementId][dependentProp.name] = dependentProp.default;
                      const inputEl = document.getElementById(`${dependentProp.name}-${elementId}`) as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
                      if (inputEl) inputEl.value = dependentProp.default;
                    } else {
                      delete this.elementParameters[elementId][dependentProp.name];
                    }
                  });
              }
            });
          }
          break;
        }
  
        case 'number': {
          const input = document.getElementById(controlId) as HTMLInputElement;
          if (input) {
            input.value = getCurrentValue() ?? prop.default;
        
            input.addEventListener('input', () => {
              const newValue = parseInt(input.value, 10);
              if (!isNaN(newValue)) {
                saveValue(newValue);
        
                const dependentDynamicSelect = config.properties.find((p: any) =>
                  p.type === 'dynamic-select' && p.options_from === paramKey
                );
        
                if (dependentDynamicSelect) {
                  const selectId = `${dependentDynamicSelect.name}-${elementId}`;
                  const select = document.getElementById(selectId) as HTMLSelectElement;
        
                  if (select) {
                    select.innerHTML = '';
                    for (let i = 0; i < newValue; i++) {
                      const option = document.createElement('option');
                      option.value = i.toString();
                      option.text = dependentDynamicSelect.options_template.replace('@index', i.toString());
                      select.appendChild(option);
                    }
        
                    this.elementParameters[elementId][dependentDynamicSelect.name] = '0';
                    select.value = '0';
                  }
        
                  this.renderSelectedConvLayerConfig(elementId, config);
                }
        
                const repeatGroup = config.properties.find((p: any) =>
                  p.type === 'conditional-repeat-group-by-index' && p.repeat === paramKey
                );
        
                if (repeatGroup) {
                  const groupName = repeatGroup.name;
                  const groupArray = this.elementParameters[elementId]?.[groupName];
                  if (Array.isArray(groupArray) && groupArray.length > newValue) {
                    this.elementParameters[elementId][groupName] = groupArray.slice(0, newValue);
                  }
        
                  const selectedIndex = parseInt(this.elementParameters[elementId]?.[repeatGroup.index] || '0', 10);
                  if (selectedIndex >= newValue) {
                    this.elementParameters[elementId][repeatGroup.index] = '0';
                  }
        
                  this.renderSelectedConvLayerConfig(elementId, config);
                }
              }
            });
          }
          break;
        }
 
        case 'select': {
          const selectEl = document.getElementById(controlId) as HTMLSelectElement;
          if (selectEl) {
            selectEl.value = getCurrentValue() ?? prop.default;
  
            selectEl.addEventListener('change', () => {
              const selectedValue = selectEl.value;
              saveValue(selectedValue);
            });
          }
          break;
        }
  
        case 'textarea': {
          const textarea = document.getElementById(controlId) as HTMLTextAreaElement;
          if (textarea) {
            textarea.value = getCurrentValue() ?? prop.default;
  
            textarea.addEventListener('input', () => {
              saveValue(textarea.value);
            });
  
            textarea.addEventListener('wheel', (e) => {
              const scrollTop = textarea.scrollTop;
              const scrollHeight = textarea.scrollHeight;
              const clientHeight = textarea.clientHeight;
              const atTop = scrollTop === 0;
              const atBottom = scrollTop + clientHeight >= scrollHeight - 1;
              const shouldStop = (e.deltaY < 0 && !atTop) || (e.deltaY > 0 && !atBottom);
              if (shouldStop) e.stopPropagation();
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
  
        case 'dynamic-select': {
          const select = document.getElementById(`${paramKey}-${elementId}`) as HTMLSelectElement;
          const layerCount = this.elementParameters[elementId]?.[prop.options_from] || 0;
  
          if (select) {
            select.innerHTML = '';
            for (let i = 0; i < layerCount; i++) {
              const option = document.createElement('option');
              option.value = i.toString();
              option.text = prop.options_template.replace('@index', i.toString());
              if (i.toString() === getCurrentValue()) option.selected = true;
              select.appendChild(option);
            }
  
            select.addEventListener('change', () => {
              saveValue(select.value);
              this.renderSelectedConvLayerConfig(elementId, config);
            });
          }
          break;
        }

        case 'multi-select': {
          const containerId = `${paramKey}-container-${elementId}`;
          const container = document.getElementById(containerId);
          if (!container) break;
        
          container.className = 'csv-columns-container';
        
          const optionsSource = prop.options || [];
        
          const dynamicOptions = prop.options_from
            ? this.elementParameters[elementId]?.[prop.options_from] || []
            : optionsSource;
        
          if (!Array.isArray(this.elementParameters[elementId][paramKey])) {
            this.elementParameters[elementId][paramKey] = dynamicOptions.map((opt: any) => {
              const name = typeof opt === 'string' ? opt : opt.name;
              return { name, selected: true };
            });
          } else {
            const currentValues = this.elementParameters[elementId][paramKey];
            dynamicOptions.forEach((opt: any) => {
              const name = typeof opt === 'string' ? opt : opt.name;
              const exists = currentValues.find((v: any) => v.name === name);
              if (!exists) {
                currentValues.push({ name, selected: true });
              }
            });
          }
          
        
          const values = this.elementParameters[elementId][paramKey];
        
          dynamicOptions.forEach((opt: any) => {
            const cleanOpt = typeof opt === 'string' ? opt : opt.name;
        
            const currentItem = values.find((v: any) => v.name === cleanOpt);
            const isSelected = currentItem?.selected ?? true;
        
            const optionEl = document.createElement('div');
            optionEl.textContent = cleanOpt;
            optionEl.className = 'column-item';
            if (isSelected) {
              optionEl.classList.add('selected');
            }
        
            this.renderer.listen(optionEl, 'click', () => {
              const item = values.find((v: any) => v.name === cleanOpt);
              if (item) {
                item.selected = !item.selected;
                optionEl.classList.toggle('selected');
        
                this.elementParameters[elementId][paramKey] = [...values];
              }
            });
        
            container.appendChild(optionEl);
          });
        
          break;
        }
        
        
      }
    });
  
    this.evaluateInitialConditionalVisibility(config, node.id);
  
    const repeatGroupProp = config.properties.find((p: any) => p.type === 'conditional-repeat-group-by-index');
    if (repeatGroupProp) {
      this.renderSelectedConvLayerConfig(elementId, config);
    }
  }
  

  private renderSelectedConvLayerConfig(elementId: string, config: any): void {
    const repeatGroupProp = config.properties.find((p: any) => p.type === 'conditional-repeat-group-by-index');
    if (!repeatGroupProp || !Array.isArray(repeatGroupProp.template)) return;
  
    const groupName = repeatGroupProp.name;
    const indexKey = repeatGroupProp.index;
  
    const layerIndex = parseInt(this.elementParameters[elementId]?.[indexKey] || '0', 10);
    const containerId = `${groupName}-container-${elementId}`;
    const container = document.getElementById(containerId);
    if (!container) return;
  
    container.innerHTML = '';
  
    if (!this.elementParameters[elementId][groupName]) {
      this.elementParameters[elementId][groupName] = [];
    }
    if (!this.elementParameters[elementId][groupName][layerIndex]) {
      this.elementParameters[elementId][groupName][layerIndex] = {};
    }
  
    const layerParams = this.elementParameters[elementId][groupName][layerIndex];
  
    for (const subProp of repeatGroupProp.template) {
      if (!subProp.conditional) {
        if (!(subProp.name in layerParams)) {
          layerParams[subProp.name] = subProp.default;
        }
      } else {
        const parentVal = layerParams[subProp.conditional.dependsOn];
        if (parentVal === subProp.conditional.value && !(subProp.name in layerParams)) {
          layerParams[subProp.name] = subProp.default;
        }
      }
    }
  
    const fieldset = document.createElement('fieldset');
    fieldset.style.border = '1px solid #ccc';
    fieldset.style.padding = '10px';
    fieldset.style.marginBottom = '10px';
  
    const legend = document.createElement('legend');
    legend.textContent = `Layer ${layerIndex} Configuration`;
    fieldset.appendChild(legend);
  
    for (const subProp of repeatGroupProp.template) {
      const subPropClone = {
        ...subProp,
        name: `${groupName}_${layerIndex}_${subProp.name}`,
        groupName: groupName,
        repeatIndex: layerIndex
      };
      const html = this.generatePropertyHTML(subPropClone, elementId);
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = html;
      Array.from(tempDiv.children).forEach(child => fieldset.appendChild(child));
    }
  
    container.appendChild(fieldset);
  
    const subPropsWithMeta = repeatGroupProp.template.map((sp: any) => ({
      ...sp,
      name: `${groupName}_${layerIndex}_${sp.name}`,
      groupName,
      repeatIndex: layerIndex
    }));
  
    this.setupDynamicInputs({ id: elementId } as any, { properties: subPropsWithMeta });
    this.evaluateInitialConditionalVisibility({ properties: subPropsWithMeta }, elementId);
  }

  private saveCurrentConvLayerParams(elementId: string, config: any): void {
    const repeatGroupProp = config.properties.find((p: any) => p.type === 'conditional-repeat-group-by-index');
    if (!repeatGroupProp) return;
  
    const groupName = repeatGroupProp.name;
    const indexKey = repeatGroupProp.index;
    const layerIndex = parseInt(this.elementParameters[elementId]?.[indexKey] || '0', 10);
  
    if (!this.elementParameters[elementId][groupName] || !this.elementParameters[elementId][groupName][layerIndex]) {
      return;
    }
  
    const layerParams = this.elementParameters[elementId][groupName][layerIndex];
  
    repeatGroupProp.template.forEach((subProp: any) => {
      const fullName = `${groupName}_${layerIndex}_${subProp.name}`;
      const input = document.getElementById(`${fullName}-${elementId}`) as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
  
      if (input) {
        let value: any = input.value;
  
        if (input.type === 'number') value = parseFloat(value);
        if (value === '' || value === undefined || value === null || isNaN(value)) value = subProp.default;
  
        layerParams[subProp.name] = value;
      }
    });
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
        const alreadyExists = this.selectedCSVFiles.some(f => f.name === file.name);
        if (!alreadyExists) {
          this.selectedCSVFiles.push(file);
        }
  
        const reader = new FileReader();
        reader.onload = (e: any) => {
          const text = e.target.result;
          const rows = text.split('\n').filter((r :any) => r.trim() !== '');
          if (rows.length < 1) return;
  
          const columns = rows[0].split(',').map((col: string) => col.trim().replace(/^"|"$/g, ''));
          const dataRows = rows.slice(1).map((r :any) => r.split(',').map((col: string) => col.trim()));
  
          const elementId = this.currentCSVElementId;
          if (!elementId) return;
  
          this.elementParameters[elementId] = {
            csvFileName: file.name,
            columns: columns.map((col :any) => ({ name: col, selected: true }))
          };
  
          const targetCandidates = ['target', 'label', 'class'];
          let targetColumn = columns.find((col :any) => targetCandidates.includes(col.toLowerCase()));
          let targetIndex = columns.indexOf(targetColumn || '');

          if (!targetColumn || targetIndex === -1) {
            targetIndex = columns.length - 1;
            targetColumn = columns[targetIndex];
          }
  
          if (targetIndex !== -1) {
            const classSet = new Set<string>();
            for (const row of dataRows) {
              const value = row[targetIndex];
              if (value) classSet.add(value);
            }
            this.elementParameters[elementId].classes = Array.from(classSet).map(cls => ({
              name: cls.trim().replace(/^"|"$/g, ''),
              selected: true
            }));
          }
             
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
            ...this.elementParameters[elementId],
            networkFileName: file.name,
            classes: ['normal', 'anomaly']
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
    if (section === 'classification' || section === 'regression' || section === 'anomalyDetection' || section === 'explainability' || section === 'monitoring') {
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
  
    const node = await this.editorRef.addElement(this.draggedNodeType!, [dropX, dropY], displayName, icon, );
    const elementId = (node as any).id;

    if (elementId) {
      this.initializeDefaultParameters(this.draggedNodeType!, elementId);
    }

    this.updateUnsavedState();
  }

  private initializeDefaultParameters(type: string, elementId: string): void {
    const elementConfig = this.getElementConfig(type);
    if (!elementConfig || !Array.isArray(elementConfig.properties)) return;
  
    this.elementParameters[elementId] = {};
  
    elementConfig.properties.forEach((prop: any) => {
      if (prop.type === 'conditional-repeat-group-by-index') {
        const numLayers = elementConfig.properties.find((p: any) => p.name === prop.repeat)?.default || 1;
        this.elementParameters[elementId][prop.name] = [];
  
        for (let i = 0; i < numLayers; i++) {
          const layerParams: any = {};
          prop.template.forEach((subProp: any) => {
            if (!subProp.conditional) {
              layerParams[subProp.name] = subProp.default;
            } else if (subProp.conditional.value === layerParams[subProp.conditional.dependsOn]) {
              layerParams[subProp.name] = subProp.default;
            }
          });
          this.elementParameters[elementId][prop.name].push(layerParams);
        }
  
        this.elementParameters[elementId][prop.index] = '0';
      } else {
        const setMultiSelectDefault = () => {
          const options = prop.options || [];
  
          if (prop.name === 'metrics' && 
              (type === 'ClassificationMonitor' || type === 'RegressionMonitor')) {
            const metricsDict: { [key: string]: boolean } = {};
            options.forEach((opt: string) => {
              metricsDict[opt] = true;
            });
            return metricsDict;
          }
  
          return options.map((opt: string) => ({
            name: opt,
            selected: true
          }));
        };
  
        if (!prop.conditional) {
          if (prop.type === 'multi-select') {
            this.elementParameters[elementId][prop.name] = setMultiSelectDefault();
          } else {
            this.elementParameters[elementId][prop.name] = prop.default;
          }
        } else {
          const dependsValue = this.elementParameters[elementId][prop.conditional.dependsOn];
          if (dependsValue === prop.conditional.value) {
            if (prop.type === 'multi-select') {
              this.elementParameters[elementId][prop.name] = setMultiSelectDefault();
            } else {
              this.elementParameters[elementId][prop.name] = prop.default;
            }
          }
        }
      }
    });
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
  
    const savedElements = await Promise.all(nodes.map(async (node :any) => {
      const elementParams = this.elementParameters[node.id] || {};
      const type = await this.editorRef.getNodeType(node.id);
  
      if (type === 'CSV' && elementParams.columns) {
        elementParams.columns = elementParams.columns.map((col: any) => ({
          name: col.name,
          selected: col.selected
        }));
      }

      if (type === 'SHAP') {
        if (elementParams.selectedClasses) {
          elementParams.selectedClasses = elementParams.selectedClasses.map((classe: any) => ({
            name: classe.name,
            selected: classe.selected
          }));
        }
      
        delete elementParams.classes;
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
  
        await this.editorRef.clearEditor();
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
    
      const node = await this.editorRef.addElement(element.type, [element.position.left, element.position.top], displayName, icon, element.id);
      
      if (element.type === 'CSV' && element.parameters?.columns) {
        this.elementParameters[element.id] = {
          ...element.parameters,
          columns: element.parameters.columns 
        };
      }

      if (element.type === 'SHAP' && element.parameters?.selectedClasses) {
        this.elementParameters[element.id] = {
          ...element.parameters,
          classes: element.parameters.selectedClasses.map((cls: any) => ({
            name: cls.name,
            selected: true
          }))
        };
      }
      
      
      
      if ((element === 'CodeProcessing' || element === 'CodeSplitter') && element.parameters?.code) {
          this.elementParameters[element.id] = {
            ...element.parameters,
            code: element.parameters.code
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
