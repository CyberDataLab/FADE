
// Angular core and common modules
import { Component, OnInit, Inject, Injector, ViewChild, ElementRef, AfterViewInit } from '@angular/core';
import { PLATFORM_ID, Renderer2 } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';

// External imports
import { NodeEditor, GetSchemes, ClassicPreset } from 'rete';
import { AngularArea2D } from 'rete-angular-plugin';
import { AreaPlugin } from 'rete-area-plugin';
import { Subscription } from 'rxjs';

// Application-specific services, DTO and create editor
import { ScenarioService } from '../../../Core/services/scenario.service';
import { Scenario } from '../../../DTOs/Scenario';
import { createEditor } from './editor';
import { ToolbarService } from '../../../Core/services/toolbar.service';

// Define Rete.js schemes and area types
type Schemes = GetSchemes<
  ClassicPreset.Node,
  ClassicPreset.Connection<ClassicPreset.Node, ClassicPreset.Node>
>;
type AreaExtra = AngularArea2D<Schemes>;

/**
 * @summary Component for building and editing scenarios visually using Rete.js.
 * 
 * This component handles the drag-and-drop UI, dynamic configuration,
 * and orchestration of nodes and their connections in a scenario.
 */
@Component({
    selector: 'app-new-scenario',
    imports: [
        CommonModule
    ],
    templateUrl: './new-scenario.component.html',
    styleUrl: './new-scenario.component.css'
})

export class NewScenarioComponent implements OnInit, AfterViewInit{

  /** @summary Configuration loaded from config.json for all node types */
  config: any = {};

  /** 
   * @summary Reference to the Rete.js editor and helper methods
   * 
   * Includes logic for adding nodes, connecting them, clearing, and destroying.
   */
  editorRef!: {
    editor: NodeEditor<Schemes>;
    area: AreaPlugin<Schemes, AreaExtra>;
    addElement: (type: string, position: [number, number], displayName?: string, icon?: string, id?: string) => Promise<ClassicPreset.Node>;
    getNodeType: (nodeId: string) => Promise<string | undefined>;
    connectNodesById: (connections: { startId: string; startOutput: string; endId: string; endInput: string }[]) => Promise<void>;
    clearEditor: () => void;
    destroy: () => void;
  };

  /** @summary Currently dragged node type from the UI palette */
  draggedNodeType: string | null = null;
  
  /** @summary Controls visibility of the right configuration panel */
  showConfigContainer = false;

  /** @summary Stores which top-level sections of the UI are expanded */
  activeSections: { [key: string]: boolean } = {};

  /** @summary Tracks the expanded state of scenario sub-categories */
  activeSubSections: { [key in 'classification' | 'regression' | 'anomalyDetection' | 'explainability' | 'monitoring']: boolean } = {
    classification: false,
    regression: false,
    anomalyDetection: false,
    explainability: false,
    monitoring: false
  };

  /** @summary Scenario loaded from the backend or newly created */
  scenario: Scenario | null = null;

  /** @summary Elements currently being dragged (for visual feedback) */
  draggedElements: HTMLElement[] = [];

  /** @summary Elements currently selected (via click/box selection) */
  selectedElements: HTMLElement[] = [];

  /** @summary Elements successfully dropped in the canvas */
  droppedElements: HTMLElement[] = [];

  /** @summary Tracks relative position for each dragged element */
  relativePositions: { element: HTMLElement; offsetX: number; offsetY: number }[] = [];

  /** @summary Indicates whether the scenario is new or being edited */
  isNewScenario: boolean = true;

  /** @summary UUID of the loaded scenario (from URL if editing) */
  scenarioId: string | null = null;

  /** @summary Files attached to CSV input nodes */
  selectedCSVFiles: File[] = [];

  /** @summary Files attached to Network input nodes */
  selectedNetworkFiles: File[] = [];

  /** @summary Files attached to JSONL input nodes */
  selectedJSONLFiles: File[] = [];

  /** @summary Stores parameters for each node by ID */
  private elementParameters: { [elementId: string]: any } = {};

  /** @summary ID of the current CSV node being configured */
  private currentCSVElementId: string | null = null;

  /** @summary ID of the current Network node being configured */
  private currentNetworkElementId: string | null = null;

  /** @summary ID of the current JSONL node being configured */
  private currentJSONLElementId: string | null = null;

  /** @summary Subscription to toolbar save events */
  private saveSub: Subscription | null = null;

  /**
   * @summary Constructor for dependency injection.
   * 
   * @param platformId Angular token to detect browser
   * @param injector Angular injector for Rete.js integration
   * @param scenarioService Service to handle scenario API interactions
   * @param route Used to extract scenario ID from the route
   * @param renderer Angular Renderer2 for DOM manipulation
   * @param http Angular HttpClient for fetching resources
   * @param toolbarService Service for save button and toolbar events
   */
  constructor(
    @Inject(PLATFORM_ID) private platformId: Object,
    private injector: Injector,
    private scenarioService: ScenarioService,
    private route: ActivatedRoute,
    private renderer: Renderer2,
    private http: HttpClient,
    private toolbarService: ToolbarService
  ) {}

  /**
   * @summary Reference to the right configuration container in the template
   */
  @ViewChild('configContainer', { static: true }) configContainer!: ElementRef;

  /**
   * @summary Reference to the canvas container used by Rete.js
   */
  @ViewChild('dropArea', { static: true }) reteContainer!: ElementRef;

  /**
   * @summary Lifecycle hook: initializes the scenario builder.
   * 
   * Sets up event listeners, loads the scenario from the backend if editing,
   * subscribes to save events, and activates UI controls.
   */
  ngOnInit() {
    if (isPlatformBrowser(this.platformId)) {
      // Prevent page scroll while using the mouse wheel in the canvas
      document.addEventListener('wheel', (e) => {
        e.preventDefault();
      }, { passive: false });

      // Bind manual save button click
      const saveScenario = document.getElementById('saveScenario');
      if (saveScenario) {
        saveScenario.addEventListener('click', () => this.saveScenario());
      }

      // Listen to save events triggered via toolbar service
      this.scenarioService.saveRequested$.subscribe(() => this.saveScenario());
      
      // Extract scenario ID if editing
      this.scenarioId = this.route.snapshot.paramMap.get('id');

      if (this.scenarioId) {
        this.isNewScenario = false;
        this.loadEditScenario(this.scenarioId);
      } 

      // Load sections defined in config.json
      this.loadSections();

      // Show save button in the toolbar
      this.toolbarService.showSaveButton();

      // Subscribe to toolbar save request
      this.saveSub = this.toolbarService.saveRequested$.subscribe(() => {
        this.saveScenario();
      });
    }
  }

  /**
   * @summary Lifecycle hook: called before component is destroyed.
   * 
   * Unsubscribes from toolbar events and hides the save button.
   */
  ngOnDestroy(): void {
    this.toolbarService.hideSaveButton();
    this.saveSub?.unsubscribe();
  }

  /**
   * @summary Lifecycle hook: initializes the visual editor (Rete.js).
   * 
   * Called after the view is initialized to ensure the DOM container is ready.
   */
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

  /**
   * @summary Deletes a node from the scenario and cleans up its data.
   * 
   * @param node The node to be removed
   */
  async deleteNode(node: ClassicPreset.Node) {
    if (!node) return;
  
    delete this.elementParameters[node.id];
  }

  /**
   * @summary Opens the configuration panel for a given node.
   * 
   * Determines the type of node, builds its configuration UI, and attaches logic.
   * 
   * @param node The node whose configuration is to be shown
   */
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
  
    // Handle custom configuration for CSV
    if (elementType === 'CSV') {
      this.handleCSVConfiguration(node, configContent);
      return;
    }
  
    // Handle monitors
    if (elementType === 'ClassificationMonitor') {
      this.handleClassificationMonitorConfiguration(node, configContent);
      return;
    }
  
    if (elementType === 'RegressionMonitor') {
      this.handleRegressionMonitorConfiguration(node, configContent);
      return;
    }
  
    // Special handling for SHAP nodes (needs upstream class detection)
    if (elementType === 'SHAP') {
      const shapId = node.id;
    
      /**
       * @summary Recursively finds the class labels from upstream nodes,
       * including anomaly models and standard classifiers.
       * 
       * @param nodeId Current node ID to traverse from
       * @returns List of class names or null
       */
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
    
          // If is a anomaly model the classes are always 'normal' and 'anomaly'
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
    
      // Store resolved classes
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
  
    // Default case for other node types
    const elementConfig = this.getElementConfig(elementType);
    if (!elementConfig) return;
  
    configContent.innerHTML = this.generateConfigHTML(elementConfig, node.id);
    this.setupDynamicInputs(node, elementConfig);
  
    this.hideContextMenu();
  }
  
  /**
   * @summary Retrieves the configuration object for a given element type.
   * 
   * This function performs a deep search within the configuration sections
   * (`dataSource`, `dataProcessing`, `dataModel`) to find a matching element
   * based on its `type`. It supports nested categories such as classification,
   * regression, explainability, anomaly detection, and monitoring.
   * 
   * Additionally, if not found in the primary sections, it checks for
   * reusable properties of type `'csv-columns-array'` as a fallback.
   * 
   * @param elementType The type of the element (e.g., 'CSV', 'SHAP', etc.)
   * 
   * @returns The configuration object for the element, or `null` if not found
   */
  private getElementConfig(elementType: string): any {
    const config = this.config;
    
    /**
     * @summary Recursively searches for the element in a given configuration object.
     * 
     * @param obj A subsection of the global configuration to search in
     * 
     * @returns The matching element config, or null
     */
    const deepSearch = (obj: any): any => {
      // Check if the current object has the type we are looking for
      if (obj.elements) {
        const found = obj.elements.find((e: any) => e.type === elementType);
        if (found) return found;
      }

      // Get classification section
      if (obj.classification) {
        const found = obj.classification.find((e: any) => e.type === elementType);
        if (found) return found;
      }

      // Get regression section
      if (obj.regression) {
        const found = obj.regression.find((e: any) => e.type === elementType);
        if (found) return found;
      }

      // Get explainability section
      if (obj.explainability) {
        const found = obj.explainability.find((e: any) => e.type === elementType);
        if (found) return found;
      }

      // Get anomaly detection section
      if (obj.anomalyDetection) {
        const found = obj.anomalyDetection.find((e: any) => e.type === elementType);
        if (found) return found;
      }

      // Get monitoring section
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

  /**
   * @summary Generates the HTML markup for a node's configuration panel.
   * 
   * This function takes the configuration schema for a node and its ID,
   * then builds the HTML structure dynamically based on the properties defined.
   * It also initializes default values for each property if not already present
   * in the `elementParameters` map.
   * 
   * Supports conditional properties and specialized types like
   * `conditional-repeat-group-by-index`.
   * 
   * @param config Configuration object for the element
   * @param elementId Unique ID of the element (node)
   * 
   * @returns A string containing the generated HTML
   */
  private generateConfigHTML(config: any, elementId: string): string {
    // Initial title for the configuration section
    let html = `<h3 style="margin-bottom: 30px;">${config.displayName} Configuration</h3>`;
  
    // Ensure an entry exists for this element in the internal parameters map
    if (!this.elementParameters[elementId]) {
      this.elementParameters[elementId] = {};
    }
    
    // Initialize default values for each property
    config.properties.forEach((prop: any) => {
      if (prop.conditional) {
        const parentValue = this.elementParameters[elementId][prop.conditional.dependsOn];

        // Only set default if condition matches and property hasn't been initialize
        if (parentValue === prop.conditional.value && !(prop.name in this.elementParameters[elementId])) {
          this.elementParameters[elementId][prop.name] = prop.default;
        }
      } else if (!(prop.name in this.elementParameters[elementId])) {
        this.elementParameters[elementId][prop.name] = prop.default;
      }
    });
    
    // If no valid properties exist, return an error block
    if (!config.properties || !Array.isArray(config.properties)) {
      return html + '<p>Configuration error</p>';
    }
  
    // Generate HTML for each property in the config
    config.properties.forEach((prop: any) => {
      if (!prop.name || !prop.type) {
        return;
      }
  
      // Render placeholder container for complex dynamic types
      if (prop.type === 'conditional-repeat-group-by-index') {
        html += `<div id="${prop.name}-container-${elementId}"></div>`;
      } else {
        // Delegate to helper function to generate standard property HTML
        html += this.generatePropertyHTML(prop, elementId);
      }
    });
  
    return html;
  }
  
  /**
   * @summary Generates the HTML string for a specific configuration property.
   * 
   * This function handles various property types (`file`, `select`, `number`, `textarea`, etc.)
   * and constructs the corresponding HTML block, incorporating labels, default values, 
   * styles, and conditional logic as necessary. Supports repeatable groups and 
   * dynamic rendering behavior.
   * 
   * @param prop Configuration object for the individual property
   * @param elementId ID of the node element this property belongs to
   * 
   * @returns A string containing the generated HTML block
   */

  private generatePropertyHTML(prop: any, elementId: string): string {
    let html = '';
    let currentValue: any = undefined;

    // Handle values from repeat groups, if applicable
    if (prop.groupName !== undefined && prop.repeatIndex !== undefined) {
      const originalName = prop.name.replace(`${prop.groupName}_${prop.repeatIndex}_`, '');
      const group = this.elementParameters[elementId]?.[prop.groupName] || [];
      currentValue = group[prop.repeatIndex]?.[originalName] ?? prop.default;
    } else {
      currentValue = this.elementParameters[elementId]?.[prop.name] ?? prop.default;
    }

    const formattedValue = currentValue !== undefined ? currentValue.toString() : prop.default;

    // Render each type of input based on `prop.type`
    switch (prop.type) {

      // Handle file input type
      case 'file':
        html += `
          <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-bottom: 60px; align-items: center;">
            <label for="${prop.name}-${elementId}">${this.formatPropertyName(prop.label || prop.name)}:</label>
            <input type="file" id="${prop.name}-${elementId}" accept="${prop.accept || '*'}" />
          </div>`;
        break;

      // Handle conditional select input type
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

      // Handle standard select input type
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
        
      // Handle dynamic select input type
      case 'dynamic-select':
        html += `
          <div style="display: flex; justify-content: space-between; gap: 10px; margin-bottom: 60px; align-items: flex-start;">
            <label for="${prop.name}-${elementId}" style="flex: 1;">${this.formatPropertyName(prop.label)}:</label>
            <select id="${prop.name}-${elementId}" style="height: 3.6em; padding: 0.75em 1em; font-size: 16px; line-height: 1.2; flex: 2; box-sizing: border-box;">
              <!-- Opciones generadas dinámicamente en setupDynamicInputs -->
            </select>
          </div>`;
        break;
        
      // Handle number input type
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

      // Handle textarea input type
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

      // Handle multi-select input type
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

  /**
   * @summary Sets the initial visibility of conditionally rendered properties.
   * 
   * Iterates through each property in the configuration and hides or shows
   * dependent input rows based on the initial value of their controlling property.
   * This supports both standard and repeatable group inputs.
   * 
   * @param config The configuration object containing the list of properties
   * @param elementId The ID of the element/node to which these properties belong
   */
  private evaluateInitialConditionalVisibility(config: any, elementId: string): void {
    config.properties.forEach((prop: any) => {
      // Skip properties without a conditional rule
      if (!prop.conditional) return;
  
      // Construct the ID of the HTML row to show/hide
      const rowId = `${prop.name}-row-${elementId}`;
      const dependentRow = document.getElementById(rowId);
      if (!dependentRow) return;
  
      // Determine if the property is inside a repeatable group
      const isInGroup = prop.groupName !== undefined && prop.repeatIndex !== undefined;

      // Retrieve the value of the controlling property (the one this property depends on)
      let controllingValue;
  
      if (isInGroup) {
        const originalName = prop.conditional.dependsOn;
        controllingValue = this.elementParameters[elementId]?.[prop.groupName]?.[prop.repeatIndex]?.[originalName];
      } else {
        controllingValue = this.elementParameters[elementId]?.[prop.conditional.dependsOn];
      }
  
      // Check if the controlling value matches the condition to show the field
      const shouldShow = controllingValue === prop.conditional.value;

      // Update the display style of the dependent row accordingly
      dependentRow.style.display = shouldShow ? 'grid' : 'none';
    });
  }
  /**
   * @summary Formats a property name for display.
   * 
   * Converts camelCase or PascalCase names into a more readable format
   * with spaces and capitalization. Also handles special cases like "With".
   * 
   * @param name The raw property name to format
   * 
   * @returns A formatted string suitable for UI labels
   */
  private formatPropertyName(name: string): string {
    return name
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, str => str.toUpperCase())
      .replace(/With/g, 'With ');
  }
  
  /**
   * @summary Formats an option name for display.
   * 
   * Handles special cases like 'True' and 'False' to ensure consistent
   * capitalization and formatting in the UI.
   * 
   * @param option The raw option string to format
   * 
   * @returns A formatted string suitable for UI display
   */
  private formatOptionName(option: string): string {
    return option === 'True' ? 'True' : 
           option === 'False' ? 'False' : 
           option;
  }
  
  /**
   * @summary Configures dynamic inputs for a given node based on its configuration schema.
   * 
   * Binds change/input listeners to each property input, updates internal state (`elementParameters`),
   * handles conditional visibility and special behaviors (e.g., repeat groups, file handling, dynamic selects).
   * 
   * @param node The node whose inputs are being set up
   * @param config The configuration object containing property definitions
   */
  private setupDynamicInputs(node: ClassicPreset.Node, config: any): void {
    const elementId = node.id;
  
    // Loop through each property defined in the configuration
    config.properties.forEach((prop: any) => {
      const paramKey = prop.name;
      const controlId = `${paramKey}-${elementId}`;
      const isInGroup = prop.groupName !== undefined && prop.repeatIndex !== undefined;
  
      // Retrieve the current value of the property from internal state
      const getCurrentValue = (): any => {
        if (isInGroup) {
          const originalName = paramKey.replace(`${prop.groupName}_${prop.repeatIndex}_`, '');
          return this.elementParameters[elementId][prop.groupName]?.[prop.repeatIndex]?.[originalName];
        } else {
          return this.elementParameters[elementId][paramKey];
        }
      };
  
      // Save a new value to internal state
      const saveValue = (value: any) => {
        if (isInGroup) {
          const originalName = paramKey.replace(`${prop.groupName}_${prop.repeatIndex}_`, '');
          this.elementParameters[elementId][prop.groupName][prop.repeatIndex][originalName] = value;
        } else {
          this.elementParameters[elementId][paramKey] = value;
        }
      };
  
      // Delete a property value from internal state
      const deleteValue = () => {
        if (isInGroup) {
          const originalName = paramKey.replace(`${prop.groupName}_${prop.repeatIndex}_`, '');
          delete this.elementParameters[elementId][prop.groupName][prop.repeatIndex][originalName];
        } else {
          delete this.elementParameters[elementId][paramKey];
        }
      };

      const propKeyWithoutPrefix = (key: string, index: number) => key.replace(`conv_layers_${index}_`, '');

      // Handle each input type
      switch (prop.type) {

        /**
         * @description File input: bind file selection event
         */
        case 'file': {
          const fileInput = document.getElementById(controlId) as HTMLInputElement;
          if (fileInput) {
            fileInput.addEventListener('change', (event: Event) => {
              const input = event.target as HTMLInputElement;
              if (input.files?.length) {
                const file = input.files[0];
                if (prop.name === 'networkFileName') {
                  this.onNetworkFileSelected(event);
                  this.currentNetworkElementId = node.id;
                }
                if(prop.name === 'jsonlFileName') {
                  this.onJSONLFileSelected(event);
                  this.currentJSONLElementId = node.id;
                }
                saveValue(file.name);
              }
            });
          }
          
          break;
        }
        
        /**
         * @description Conditional select: affects visibility of dependent fields
         */
        case 'conditional-select': {
          const selectId = `${paramKey}-select-${elementId}`;
          const select = document.getElementById(selectId) as HTMLSelectElement;
        
          if (select) {
            select.value = getCurrentValue() ?? prop.default;
        
            select.addEventListener('change', () => {
              const newValue = select.value;
              this.saveCurrentLayerParams(elementId, config);
              saveValue(newValue);
              this.renderSelectedLayerConfig(elementId, config);
        
              // Handle dependencies for repeat group or standard fields
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
  
        /**
         * @description Number input: may trigger dynamic selects or repeat groups
         */
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
        
                // Update dependent dynamic select
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
        
                  this.renderSelectedLayerConfig(elementId, config);
                }
        
                // Adjust repeat group array size if applicable
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
        
                  this.renderSelectedLayerConfig(elementId, config);
                }
              }
            });
          }
          break;
        }
 
        /**
         * @description Static select input
         */
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
  
        /**
         * @description Textarea input with zoom controls and scroll management
         */
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
  
        /**
         * @description Dynamic select based on another parameter's value
         */
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
              this.renderSelectedLayerConfig(elementId, config);
            });
          }
          break;
        }

        /**
         * @description Multi-select input with toggleable items
         */
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
  
    // Evaluate initial conditional visibility for all conditionally rendered fields
    this.evaluateInitialConditionalVisibility(config, node.id);
  
    // If the component contains repeatable sections, render the current configuration
    const repeatGroupProp = config.properties.find((p: any) => p.type === 'conditional-repeat-group-by-index');
    if (repeatGroupProp) {
      this.renderSelectedLayerConfig(elementId, config);
    }
  }
  
  /**
   * @summary Renders the parameter configuration fields for a selected convolutional layer (or similar repeat group).
   * 
   * Dynamically constructs and injects a form-like fieldset into the DOM, corresponding to the configuration of
   * a specific indexed element within a `conditional-repeat-group-by-index`. Initializes default values if missing,
   * attaches event listeners, and enforces conditional visibility of fields.
   * 
   * @param elementId The unique identifier of the node being configured
   * @param config The full configuration object that includes property definitions
   */
  private renderSelectedLayerConfig(elementId: string, config: any): void {

    // Find the special property that defines a repeatable group
    const repeatGroupProp = config.properties.find((p: any) => p.type === 'conditional-repeat-group-by-index');
    if (!repeatGroupProp || !Array.isArray(repeatGroupProp.template)) return;
  
    const groupName = repeatGroupProp.name; // e.g., "conv_layers"
    const indexKey = repeatGroupProp.index; // e.g., "selectedLayer"
  
    // Determine which index is currently selected (e.g., which layer)
    const layerIndex = parseInt(this.elementParameters[elementId]?.[indexKey] || '0', 10);

    // Get the container div where the layer config will be injected
    const containerId = `${groupName}-container-${elementId}`;
    const container = document.getElementById(containerId);
    if (!container) return;
  
    container.innerHTML = '';
  
    // Ensure internal state structure exists for this group and index
    if (!this.elementParameters[elementId][groupName]) {
      this.elementParameters[elementId][groupName] = [];
    }
    if (!this.elementParameters[elementId][groupName][layerIndex]) {
      this.elementParameters[elementId][groupName][layerIndex] = {};
    }
  
    const layerParams = this.elementParameters[elementId][groupName][layerIndex];
  
    // Initialize missing default values for the layer
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
  
    // Create the fieldset container with a label
    const fieldset = document.createElement('fieldset');
    fieldset.style.border = '1px solid #ccc';
    fieldset.style.padding = '10px';
    fieldset.style.marginBottom = '10px';
  
    const legend = document.createElement('legend');
    legend.textContent = `Layer ${layerIndex} Configuration`;
    fieldset.appendChild(legend);
  
    // Render HTML for each property in the template
    for (const subProp of repeatGroupProp.template) {
      const subPropClone = {
        ...subProp,
        name: `${groupName}_${layerIndex}_${subProp.name}`, // e.g., conv_layers_0_kernelSize
        groupName: groupName,
        repeatIndex: layerIndex
      };
      const html = this.generatePropertyHTML(subPropClone, elementId);

      // Inject the generated HTML into a temporary div and append to fieldset
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = html;
      Array.from(tempDiv.children).forEach(child => fieldset.appendChild(child));
    }
  
    // Add the fully built fieldset into the DOM
    container.appendChild(fieldset);
  
    // Prepare the sub-properties for input binding and conditional logic
    const subPropsWithMeta = repeatGroupProp.template.map((sp: any) => ({
      ...sp,
      name: `${groupName}_${layerIndex}_${sp.name}`,
      groupName,
      repeatIndex: layerIndex
    }));
  
    // Setup dynamic behavior and listeners
    this.setupDynamicInputs({ id: elementId } as any, { properties: subPropsWithMeta });

    // Ensure proper visibility of conditional fields
    this.evaluateInitialConditionalVisibility({ properties: subPropsWithMeta }, elementId);
  }

  /**
  * @summary Saves the current user-edited values from the UI inputs of a repeatable group (e.g., neural network layer).
  * 
  * Traverses the DOM for a specific layer (identified by index) and extracts input values based on the configuration
  * template. Values are parsed and validated before updating the internal `elementParameters` structure.
  * 
  * @param elementId The unique identifier of the node whose parameters are being saved
  * @param config The full configuration object containing the repeat group structure
  */
  private saveCurrentLayerParams(elementId: string, config: any): void {

    // Look for the special group definition with type 'conditional-repeat-group-by-index'
    const repeatGroupProp = config.properties.find((p: any) => p.type === 'conditional-repeat-group-by-index');
    if (!repeatGroupProp) return;
  
    const groupName = repeatGroupProp.name;    // e.g., "conv_layers"
    const indexKey = repeatGroupProp.index;    // e.g., "selectedLayer"
    const layerIndex = parseInt(this.elementParameters[elementId]?.[indexKey] || '0', 10);
  
    // Ensure the layer array and the current index are initialized
    if (!this.elementParameters[elementId][groupName] || !this.elementParameters[elementId][groupName][layerIndex]) {
      return;
    }
  
    const layerParams = this.elementParameters[elementId][groupName][layerIndex];
  
    // Iterate through each property defined for the layer
    repeatGroupProp.template.forEach((subProp: any) => {
      const fullName = `${groupName}_${layerIndex}_${subProp.name}`;
      const input = document.getElementById(`${fullName}-${elementId}`) as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
  
      if (input) {
        let value: any = input.value;
  
        // If it's a numeric input, parse to float
        if (input.type === 'number') value = parseFloat(value);

        // If value is empty, invalid or NaN, fallback to default
        if (value === '' || value === undefined || value === null || isNaN(value)) value = subProp.default;
  
        // Update the in-memory parameter structure
        layerParams[subProp.name] = value;
      }
    });
  }

  /**
   * @summary Renders the configuration panel for a CSV node.
   * 
   * Displays a file input for uploading CSV files and initializes column selection UI
   * if the CSV has already been parsed previously.
   * 
   * @param node The Rete.js node associated with the CSV file
   * @param configContent The HTML container element where the configuration UI should be rendered
   */
  private handleCSVConfiguration(node: ClassicPreset.Node, configContent: HTMLElement): void {
    // Set the title and instruction message
    configContent.innerHTML = `<h3>CSV file configuration</h3><p>Please select a CSV file:</p> <div id="csv-columns-selection"></div>`;
    
    // Create file input for CSV upload with a ".csv" filter and bind the handler
    const input = this.createFileInput('csv-upload', '.csv', (e) => this.onCSVFileSelected(e));

    // Create a DOM element that will show the selected filename
    const fileNameElement = this.createFileNameElement();
    
    // Append file input and filename display to the configuration UI
    configContent.appendChild(input);
    configContent.appendChild(fileNameElement);
    
    // Set the ID of the current CSV node (used internally to track context)
    this.currentCSVElementId = node.id;

    // If this node has already loaded column metadata, update the UI to show it
    if (this.elementParameters[node.id]?.columns) {
      this.updateCSVColumnSelectionUI(
        Object.keys(this.elementParameters[node.id].columns), 
        node.id
      );
    }
  }
  
  /**
   * @summary Configures the UI for a classification monitor node.
   * 
   * Renders a selection interface for standard classification metrics.
   * 
   * @param node The classification monitor node
   * @param configContent The container element where the configuration is rendered
   */
  private handleClassificationMonitorConfiguration(node: ClassicPreset.Node, configContent: HTMLElement): void {

    // Set the title and description for the configuration panel
    configContent.innerHTML = `<h3>Classification Monitor Configuration</h3><p>Select metrics to monitor:</p><div id="metrics-selection"></div>`;
    
    // Define the available classification metrics
    const metrics = ['f1Score', 'accuracy', 'recall', 'precision', 'confusionMatrix'];

    // Render metric selection UI
    this.updateMetricsSelectionUI(metrics, node.id);
  }

  /**
   * @summary Configures the UI for a regression monitor node.
   * 
   * Displays options for selecting standard regression metrics.
   * 
   * @param node The regression monitor node
   * @param configContent The container element where the configuration is rendered
   */
  private handleRegressionMonitorConfiguration(node: ClassicPreset.Node, configContent: HTMLElement): void {

    // Set the title and description for the configuration panel
    configContent.innerHTML = `<h3>Regression Monitor Configuration</h3><p>Select metrics to monitor:</p><div id="metrics-selection"></div>`;
   
    // Define the available regression metrics
    const metrics = ['mse', 'rmse', 'mae', 'r2', 'msle'];

    // Render metric selection UI
    this.updateMetricsSelectionUI(metrics, node.id);
  }
  
  /**
   * @summary Creates an HTML file input element with a custom event handler.
   * 
   * Used for uploading files such as CSV or PCAP files in node configuration panels.
   * 
   * @param id The ID to assign to the input element
   * @param accept A comma-separated list of accepted MIME types or extensions (e.g. ".csv")
   * @param handler The function to execute on file selection (`change` event)
   * 
   * @returns The configured HTMLInputElement
   */
  private createFileInput(id: string, accept: string, handler: (e: Event) => void): HTMLInputElement {
    const input = document.createElement('input');
    input.type = 'file';
    input.id = id;
    input.accept = accept;
    input.addEventListener('change', handler);
    return input;
  }
  
  /**
   * @summary Creates a paragraph element to display the selected filename.
   * 
   * Typically placed below a file input to show which file was selected.
   * 
   * @returns A <p> element with an assigned ID
   */
  private createFileNameElement(): HTMLElement {
    const fileNameElement = document.createElement('p');
    fileNameElement.id = 'file-name';
    return fileNameElement;
  }

  /**
   * @summary Handles the selection of a CSV file and extracts its structure.
   * 
   * Parses the selected CSV file, extracts the column names, and infers class labels if applicable.
   * Updates the corresponding node's configuration with the file name, available columns, and detected classes.
   * 
   * @param event The file input `change` event triggered when a user selects a CSV file
   */
  onCSVFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input && input.files) {
      const file = input.files[0];

      // Proceed only if it's a CSV file
      if (file && file.name.endsWith('.csv')) {

        // Prevent duplicate file loading
        const alreadyExists = this.selectedCSVFiles.some(f => f.name === file.name);
        if (!alreadyExists) {
          this.selectedCSVFiles.push(file);
        }
  
        const reader = new FileReader();

        // Callback when file is successfully read
        reader.onload = (e: any) => {
          const text = e.target.result;

          // Split file content into lines, removing empty ones
          const rows = text.split('\n').filter((r :any) => r.trim() !== '');
          if (rows.length < 1) return;
  
          // Extract column names from the header row
          const columns = rows[0].split(',').map((col: string) => col.trim().replace(/^"|"$/g, ''));

          // Parse remaining rows as data
          const dataRows = rows.slice(1).map((r :any) => r.split(',').map((col: string) => col.trim()));
  
          const elementId = this.currentCSVElementId;
          if (!elementId) return;
  
          // Initialize the CSV node's parameters with file name and selected columns
          this.elementParameters[elementId] = {
            csvFileName: file.name,
            columns: columns.map((col :any) => ({ name: col, selected: true }))
          };
  
          // Attempt to auto-detect the target column using common naming conventions
          const targetCandidates = ['target', 'label', 'class'];
          let targetColumn = columns.find((col :any) => targetCandidates.includes(col.toLowerCase()));
          let targetIndex = columns.indexOf(targetColumn || '');

          // Fallback: use last column if no candidate matched
          if (!targetColumn || targetIndex === -1) {
            targetIndex = columns.length - 1;
            targetColumn = columns[targetIndex];
          }
  
          // Extract unique class values for the detected target column
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
          
          // Update the visual UI for column selection
          this.updateCSVColumnSelectionUI(columns, elementId);
        };
  
        // Trigger file read as text
        reader.readAsText(file);
      }
    }
  }
  
  /**
   * @summary Updates the UI for CSV column selection based on the parsed file.
   * 
   * Renders a list of column names as clickable elements that allow users to toggle
   * which columns are selected. Updates the internal state accordingly.
   * 
   * @param columns An array of column names extracted from the CSV file
   * @param elementId The ID of the node element being configured
   */
  updateCSVColumnSelectionUI(columns: string[], elementId: string): void {

    // Locate the container where configuration content is injected
    const configContent = this.configContainer?.nativeElement.querySelector('.config-content');
    if (!configContent) return;
  
    // Try to reuse the existing column selection div, or create a new one
    let columnSelectionDiv = document.getElementById('csv-columns-container');
    if (!columnSelectionDiv) {
      columnSelectionDiv = this.renderer.createElement('div');
      this.renderer.setAttribute(columnSelectionDiv, 'id', 'csv-columns-container');
      this.renderer.setAttribute(columnSelectionDiv, 'class', 'csv-columns-container');
    } else {
      // Clear previous column elements if any
      columnSelectionDiv.innerHTML = '';
    }
  
    // Initialize column data if not already present
    if (!this.elementParameters[elementId]?.columns) {
      this.elementParameters[elementId] = { 
        columns: columns.map(col => ({ name: col.trim(), selected: true })) 
      };
    }
  
    // Iterate over each column to create toggleable UI elements
    this.elementParameters[elementId].columns.forEach((col: any) => {
      const columnElement = this.renderer.createElement('div');
      this.renderer.setAttribute(columnElement, 'class', 'column-item');

      // Apply visual 'selected' class if the column is marked as selected
      if (col.selected) {
        this.renderer.addClass(columnElement, 'selected');
      }

      // Insert the column name as the element's text
      const columnText = this.renderer.createText(col.name);
      this.renderer.appendChild(columnElement, columnText);

      // Add click handler to toggle selection status
      this.renderer.listen(columnElement, 'click', () => {
        col.selected = !col.selected;
        columnElement.classList.toggle('selected');
        
        // Force change detection by creating a new reference
        this.elementParameters[elementId].columns = [...this.elementParameters[elementId].columns];
      });

      // Append the column UI element to the container
      this.renderer.appendChild(columnSelectionDiv, columnElement);
    });
  
    // Finally, insert the full container into the config UI
    this.renderer.appendChild(configContent, columnSelectionDiv);
  }

  /**
   * @summary Handles the selection of a .pcap network file from an input element.
   * 
   * Validates the file type, avoids duplicates, parses the file contents, and extracts
   * column information and default class labels for further configuration.
   * 
   * Updates the `elementParameters` map with the file name and a default class list.
   * 
   * @param event The file selection event triggered by an input element
   */
  onNetworkFileSelected(event: Event): void {

    // Extract the input element from the event
    const input = event.target as HTMLInputElement;

    // Proceed only if a file is selected
    if (input && input.files) {
      const file = input.files[0];

      // Ensure the selected file has a .pcap extension
      if (file && file.name.endsWith('.pcap')) {
        const file = input.files[0];

        // Prevent duplicate entries in the selected file list
        const alreadyExists = this.selectedNetworkFiles.some(f => f.name === file.name);
        if (!alreadyExists) {
          this.selectedNetworkFiles.push(file);
        }
        
        // Read the file contents as plain text
        const reader = new FileReader();
        reader.onload = (e: any) => {
          const text = e.target.result;
          const rows = text.split('\n');

          // Ensure the file has at least one row (header)
          if (rows.length < 1) return;
          
          // Parse and clean the header columns
          const columns = rows[0].split(',').map((col: string) => col.trim().replace(/^"|"$/g, ''));
  
          // Identify the target element ID associated with this file
          const elementId = this.currentNetworkElementId;
          if (!elementId) return;
          
          // Update the internal parameter map with the file name and default class labels
          this.elementParameters[elementId] = {
            ...this.elementParameters[elementId],  // Preserve any existing config
            networkFileName: file.name,
            classes: ['normal', 'anomaly']  // Default class labels for network data
          };
        };

        // Trigger the file reading process
        reader.readAsText(file);
      }
    }
  }

  /**
   * @summary Handles the selection of a .jsonl file from an input element.
   * 
   * Validates the file type, avoids duplicates, parses the file contents, and extracts
   * column information and default class labels for further configuration.
   * 
   * Updates the `elementParameters` map with the file name and a default class list.
   * 
   * @param event The file selection event triggered by an input element
   */
  onJSONLFileSelected(event: Event): void {

    // Extract the input element from the event
    const input = event.target as HTMLInputElement;

    // Proceed only if a file is selected
    if (input && input.files) {
      const file = input.files[0];

      // Ensure the selected file has a .pcap extension
      if (file && file.name.endsWith('.jsonl')) {
        const file = input.files[0];

        // Prevent duplicate entries in the selected file list
        const alreadyExists = this.selectedJSONLFiles.some(f => f.name === file.name);
        if (!alreadyExists) {
          this.selectedJSONLFiles.push(file);
        }
        
        // Read the file contents as plain text
        const reader = new FileReader();
        reader.onload = (e: any) => {
          const text = e.target.result;
          const rows = text.split('\n');

          // Ensure the file has at least one row (header)
          if (rows.length < 1) return;
          
          // Parse and clean the header columns
          const columns = rows[0].split(',').map((col: string) => col.trim().replace(/^"|"$/g, ''));
  
          // Identify the target element ID associated with this file
          const elementId = this.currentJSONLElementId;

          if (!elementId) return;
          
          // Update the internal parameter map with the file name and default class labels
          this.elementParameters[elementId] = {
            ...this.elementParameters[elementId],  // Preserve any existing config
            jsonlFileName: file.name,
            classes: ['normal', 'anomaly']  // Default class labels for network data
          };
        };

        // Trigger the file reading process
        reader.readAsText(file);
      }
    }
  }

  /**
   * @summary Renders the UI to allow the user to select which classification or regression metrics to monitor.
   * 
   * Creates a toggle interface where each metric is displayed as a clickable element.
   * Clicking toggles the selection state, which is stored in `elementParameters[elementId].metrics`.
   * 
   * If no previous configuration exists, all metrics are selected by default.
   *
   * @param metrics An array of available metric names to display (e.g., ['accuracy', 'f1Score'])
   * @param elementId The unique ID of the element whose configuration is being edited
   */
  updateMetricsSelectionUI(metrics: string[], elementId: string): void {

    // Locate the config container where metric options will be inserted
    const configContent = this.configContainer?.nativeElement.querySelector('.config-content');
    if (!configContent) return;
  
    // Try to find an existing metrics container, or create a new one
    let metricsDiv = document.getElementById('metrics-container');
    
    if (!metricsDiv) {
      metricsDiv = this.renderer.createElement('div');
      this.renderer.setAttribute(metricsDiv, 'id', 'metrics-container');
      this.renderer.setAttribute(metricsDiv, 'class', 'metrics-container');
    } else {
      metricsDiv.innerHTML = '';
    }
  
    // Initialize default metric values if not already defined for this node
    if (!this.elementParameters[elementId]) {
      this.elementParameters[elementId] = { metrics: {} };
      metrics.forEach(metric => {
        this.elementParameters[elementId].metrics[metric] = true;
      });
    }
  
    // Get current selected state of metrics for the given element
    const storedMetrics = this.elementParameters[elementId].metrics;
  
    // Create a clickable UI element for each metric
    metrics.forEach(metric => {
      const metricElement = this.renderer.createElement('div');
      this.renderer.setAttribute(metricElement, 'class', `metric-item ${storedMetrics[metric] ? 'selected' : ''}`);
      
      const metricText = this.renderer.createText(metric);
      this.renderer.appendChild(metricElement, metricText);
  
      // Toggle metric selection on click
      this.renderer.listen(metricElement, 'click', () => {
        storedMetrics[metric] = !storedMetrics[metric];
        metricElement.classList.toggle('selected');

        // Update stored config with shallow copy to trigger change detection if needed
        this.elementParameters[elementId].metrics = { ...storedMetrics };
      });
  
      // Add metric element to the container
      this.renderer.appendChild(metricsDiv, metricElement);
    });
  
    // Finally, append the container to the config panel
    this.renderer.appendChild(configContent, metricsDiv);
  }

  /**
   * @summary Closes the right-side configuration panel by removing its `show` class.
   */
  closeConfig(): void {
    if (this.configContainer) {
      this.configContainer.nativeElement.classList.remove('show'); 
    }
  }
  
  /**
   * @summary Hides the custom right-click context menu if it exists in the DOM.
   */
  hideContextMenu(): void {
    const menu = document.getElementById('context-menu');
    if (menu) {
      menu.style.display = 'none';  
    }
  }

  /**
   * @summary Loads the visual node configuration from `assets/config.json` and stores it in `this.config`.
   */
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

  /**
   * @summary Updates the scenario service to indicate whether there are unsaved changes
   * based on whether any elements have been dropped.
   */
  updateUnsavedState() {
    this.scenarioService.setUnsavedChanges(this.droppedElements.length > 0);
  }

  /**
   * @summary Toggles the visibility of a main section in the left panel.
   * 
   * @param sectionName The name of the section to toggle (e.g., 'dataModel', 'dataProcessing')
   */
  toggleSection(sectionName: string) {
    this.activeSections[sectionName] = !this.activeSections[sectionName];
  }

  /**
   * @summary Toggles visibility of a subsection in the left panel (e.g., classification, regression).
   * Only applies to known categories.
   * 
   * @param section The name of the subsection to toggle.
   */
  toggleSubSection(section: string): void {
    if (
      section === 'classification' ||
      section === 'regression' ||
      section === 'anomalyDetection' ||
      section === 'explainability' ||
      section === 'monitoring'
    ) {
      this.activeSubSections[section] = !this.activeSubSections[section];
    }
  }
  
  /**
   * @summary Adds `dragstart` and `dragend` listeners to all draggable node options in the left panel.
   */
  addDragEventListeners() {
    const draggableElements = document.querySelectorAll('.option');
  
    draggableElements.forEach((element: Element) => {
      const htmlElement = element as HTMLElement;
  
      htmlElement.addEventListener('dragstart', (event) => this.onDragStart(event, false));
      htmlElement.addEventListener('dragend', (event) => this.onDragEnd(event));
    });
  }

  /**
   * @summary Handles the drag start event for a node from the sidebar or workspace.
   * If the element is from the sidebar, it creates a clone and tracks it.
   * If it's from the workspace, it tracks the currently selected elements.
   * 
   * @param event The drag start event
   * @param isWorkspace Whether the dragged element is from the workspace (`true`) or sidebar (`false`)
   */
  onDragStart(event: DragEvent, isWorkspace: boolean): void {
    const target = event.target as HTMLElement;

    // Get the node type from the dragged element
    this.draggedNodeType = target.getAttribute('data-type');

    if (target) {
      if (!isWorkspace) {

        // If dragging from sidebar: clone the element and attach drag events
        const clone = target.cloneNode(true) as HTMLElement;
        clone.addEventListener('dragstart', (e) => this.onDragStart(e, true));
        clone.addEventListener('dragend', (e) => this.onDragEnd(e));

        // Store the cloned element as the dragged one
        this.draggedElements = [clone];
      } else {

        // If dragging from workspace: use selected elements or the target
        this.draggedElements = this.selectedElements.length > 0 ? [...this.selectedElements] : [target];
      }
  
      // Calculate initial relative positions for each dragged element
      this.relativePositions = this.draggedElements.map((element) => {
        const rect = element.getBoundingClientRect();
        return { element, offsetX: 0, offsetY: 0 };
      });
  
      // Setup drag image to avoid default ghost image
      if (event.dataTransfer) {
        event.dataTransfer.setData('text/plain', '');
        event.dataTransfer.setDragImage(target, 0, 0);
      }
  
      // If multiple elements are selected, calculate offsets based on first one
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

  /**
   * @summary Clears the currently dragged elements after a drag ends.
   * 
   * @param event The drag end event
   */
  onDragEnd(event: DragEvent) {
    this.draggedElements = []; 
  }

  /**
   * @summary Prevents the default behavior to allow dropping elements on the target area.
   * 
   * @param event The drag over event
   */
  onDragOver(event: DragEvent) {
    event.preventDefault();
  }
  
  /**
   * @summary Handles the drop event when a node is dragged from the sidebar into the canvas.
   * Retrieves the node configuration, creates the visual element, and initializes its parameters.
   * 
   * @param event The drop event triggered on the canvas
   */
  async onDrop(event: DragEvent) {

    // Prevent default behavior to allow dropping
    event.preventDefault();

    // Get the exact drop coordinates relative to the canvas
    const [dropX, dropY] = this.getDropCoordinates(event);

    // Find node configuration info from config.json using the dragged node type
    const nodeInfo = this.findElementInfoByType(this.draggedNodeType!);

    // If the node type is not defined in the config, log an error and abort
    if (!nodeInfo) {
      console.error('Elemento no encontrado en config.json para tipo:', this.draggedNodeType);
      return;
    }

    const { displayName, icon } = nodeInfo;
  
    // Add the visual element to the editor at the drop coordinates
    const node = await this.editorRef.addElement(this.draggedNodeType!, [dropX, dropY], displayName, icon, );

    // Get the ID of the newly created element
    const elementId = (node as any).id;

    // If the element has an ID, initialize its default configuration parameters
    if (elementId) {
      this.initializeDefaultParameters(this.draggedNodeType!, elementId);
    }

    // Mark the scenario as having unsaved changes
    this.updateUnsavedState();
  }

  /**
   * @summary Initializes the default parameters for a given node type and element ID.
   * It handles regular properties, conditional properties, multi-selects, and
   * conditional repeatable groups (e.g., convolutional layers).
   * 
   * @param type The node type as defined in config.json
   * @param elementId The unique ID of the node instance being configured
   */
  private initializeDefaultParameters(type: string, elementId: string): void {

    // Retrieve the configuration object for the given node type
    const elementConfig = this.getElementConfig(type);
    if (!elementConfig || !Array.isArray(elementConfig.properties)) return;
  
    // Initialize the parameters object for the given node ID
    this.elementParameters[elementId] = {};
  
    // Iterate over all defined properties in the config
    elementConfig.properties.forEach((prop: any) => {

      // Handle special case: conditional repeat group (e.g., Conv layers)
      if (prop.type === 'conditional-repeat-group-by-index') {

        // Determine how many layers to initialize by checking the controlling "repeat" property
        const numLayers = elementConfig.properties.find((p: any) => p.name === prop.repeat)?.default || 1;
        this.elementParameters[elementId][prop.name] = [];
  
        for (let i = 0; i < numLayers; i++) {
          const layerParams: any = {};

          // Initialize each property inside the template for the current layer
          prop.template.forEach((subProp: any) => {
            if (!subProp.conditional) {
              layerParams[subProp.name] = subProp.default;
            } else if (subProp.conditional.value === layerParams[subProp.conditional.dependsOn]) {
              layerParams[subProp.name] = subProp.default;
            }
          });

          // Store the initialized parameters for the layer
          this.elementParameters[elementId][prop.name].push(layerParams);
        }
  
        // Initialize the currently selected index to '0'
        this.elementParameters[elementId][prop.index] = '0';
      } else {

        // Default generator for multi-select fields
        const setMultiSelectDefault = () => {
          const options = prop.options || [];
  
          // Special case: for monitor nodes, mark all metrics as selected
          if (prop.name === 'metrics' && 
              (type === 'ClassificationMonitor' || type === 'RegressionMonitor')) {
            const metricsDict: { [key: string]: boolean } = {};
            options.forEach((opt: string) => {
              metricsDict[opt] = true;
            });
            return metricsDict;
          }
  
          // Default: return array of selected options
          return options.map((opt: string) => ({
            name: opt,
            selected: true
          }));
        };
  
        // If the property is not conditional, apply its default value
        if (!prop.conditional) {
          if (prop.type === 'multi-select') {
            this.elementParameters[elementId][prop.name] = setMultiSelectDefault();
          } else {
            this.elementParameters[elementId][prop.name] = prop.default;
          }
        } else {

          // If conditional, check if the dependency is met before setting default
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

  /**
   * @summary Calculates the drop coordinates relative to the Rete.js canvas.
   * 
   * This function translates the raw screen coordinates from the drop event
   * into the coordinate space of the editor canvas, accounting for zoom (`k`)
   * and pan (`x`, `y`) transformations applied to the area.
   * 
   * @param event The drag-and-drop event containing mouse position
   * @returns A tuple with [x, y] coordinates in the editor's internal space
   */
  getDropCoordinates(event: DragEvent): [number, number] {

    // Get the bounding rectangle of the editor container
    const rect = this.reteContainer.nativeElement.getBoundingClientRect();
  
    // Calculate cursor position relative to the container
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
  
    // Get the current transformation applied to the editor canvas (pan & zoom)
    const transform = this.editorRef.area.area.transform;
  
    // Apply inverse transform to get the coordinates in editor space
    const transformedX = (x - transform.x) / transform.k;
    const transformedY = (y - transform.y) / transform.k;
  
    return [transformedX, transformedY];
  }

  /**
   * @summary Retrieves the display name and icon for a node type from the configuration.
   * 
   * This function performs a deep traversal of the `config.sections` object to
   * find the element that matches the given type. It supports nested structures
   * (like `dataSource`, `dataProcessing`, etc.) with sub-categories.
   * 
   * @param type The string identifier for the node type (e.g., 'CSV', 'RandomForest')
   * 
   * @returns An object containing `displayName` and `icon` if found, otherwise `null`
   */
  findElementInfoByType(type: string): { displayName: string, icon: string } | null {
    const sections = this.config.sections;
    for (const sectionKey in sections) {
      const section = sections[sectionKey];

      // Some sections may be arrays directly, others objects with arrays as values
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

  /**
   * @summary Serializes the current scenario design (nodes and connections) into a plain object.
   * 
   * This function iterates over all existing nodes in the editor, extracting their type,
   * parameters, and visual position. It also captures connections between nodes.
   * Special handling is performed for CSV and SHAP nodes to ensure their internal structures 
   * are stored in a consistent and minimal format.
   * 
   * @returns A Promise that resolves to an object containing `elements` and `connections`
   */
  async getCurrentDesign(): Promise<any> {

    // Retrieve all nodes currently present in the editor
    const nodes = this.editorRef.editor.getNodes();
  
    // Serialize each node asynchronously
    const savedElements = await Promise.all(nodes.map(async (node :any) => {

      // Retrieve current parameters of the node
      const elementParams = this.elementParameters[node.id] || {};

      // Determine the node type (e.g., CSV, SHAP, Model, etc.)
      const type = await this.editorRef.getNodeType(node.id);
  
      // Special handling for CSV nodes: clean up column definitions
      if (type === 'CSV' && elementParams.columns) {
        elementParams.columns = elementParams.columns.map((col: any) => ({
          name: col.name,
          selected: col.selected
        }));
      }

      // Special handling for SHAP nodes: retain only selected classes, drop all class definitions
      if (type === 'SHAP') {
        if (elementParams.selectedClasses) {
          elementParams.selectedClasses = elementParams.selectedClasses.map((classe: any) => ({
            name: classe.name,
            selected: classe.selected
          }));
        }
      
        // Remove `classes` to avoid storing unnecessary upstream info
        delete elementParams.classes;
      }

      // Get the node's visual position on the canvas
      const nodeView = this.editorRef.area.nodeViews.get(node.id);
      const position = nodeView?.position;
  
      if (!position) {
        throw new Error(`No se pudo obtener la posición del nodo con ID: ${node.id}`);
      }
  
      // Return the serialized node structure
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
  
    // Extract all connections between nodes
    const connections = this.editorRef.editor.getConnections();
  
    const savedConnections = connections.map((conn: any) => ({
      startId: conn.source,
      startOutput: conn.sourceOutput,
      endId: conn.target,
      endInput: conn.targetInput
    }));
  
    // Return the full serialized design
    return {
      elements: savedElements,
      connections: savedConnections,
    };
  }
  
  /**
   * @summary Handles the saving of a scenario, either by creating a new one or updating an existing one.
   * 
   * This method serializes the current design (nodes and connections), and then:
   * - If the scenario is new, it prompts the user for a name and creates it via the `ScenarioService`.
   * - If the scenario already exists, it updates it using the current UUID.
   * 
   * It also ensures CSV and PCAP files are sent along with the request, and handles error reporting.
   * 
   * @returns A Promise that resolves when the save operation completes
   */
  async saveScenario(): Promise<void> {

    // Generate the current visual design as JSON
    const design = await this.getCurrentDesign();
  
    // Case 1: It's a new scenario
    if (this.isNewScenario) {

      // Ask the user for a name for the new scenario
      const name = window.prompt('Please enter the name of the scenario:');
  
      if (name) {
        // Save the scenario via the service with name, design, and attached files
        this.scenarioService.saveScenario(
          name,
          design,
          this.selectedCSVFiles || [],
          this.selectedNetworkFiles || [],
          this.selectedJSONLFiles || []
        ).subscribe({
          next: (response: any) => {

            // Notify the user and update internal state
            alert('Scenario saved correctly.');
            this.scenarioId = response.uuid;
            this.isNewScenario = false;
            this.scenarioService.setUnsavedChanges(false);
          },
          error: (error: any) => {

            // Show any backend error received
            const errorMsg = error?.error?.error || 'Unexpected error';
            alert('Error creating scenario: ' + JSON.stringify(errorMsg));
          }
        });
      } else {

        // If the user cancelled or gave no name
        alert('Error while saving the scenario, you must provide a name.');
      }
  
    } else {

      // Case 2: It's an existing scenario
      if (this.scenarioId != null) {

        // Send updated design and files to the backend
        this.scenarioService.editScenario(
          this.scenarioId,
          design,
          this.selectedCSVFiles || [],
          this.selectedNetworkFiles || [],
          this.selectedJSONLFiles || []
        ).subscribe({
          next: () => {

            // Notify user and reset unsaved flag
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

  /**
   * @summary Loads and initializes an existing scenario into the visual editor.
   * 
   * This method retrieves a scenario from the backend using its UUID, parses the design data,
   * clears the current editor, and reconstructs the elements and connections in the UI.
   * 
   * @param uuid - The unique identifier of the scenario to load
   * 
   * @returns A promise that resolves once the scenario has been fully loaded into the editor
   */
  async loadEditScenario(uuid: string): Promise<void> {

    // Call the service to fetch the scenario by its UUID
    this.scenarioService.getScenarioById(uuid).subscribe(
      async (response: Scenario) => {

        // Store the received scenario in the component's state
        this.scenario = response;
        
        // Parse the design JSON if it is a string, otherwise use it directly
        const designData = typeof this.scenario.design === 'string' 
          ? JSON.parse(this.scenario.design) 
          : this.scenario.design;
  
        // Clear all existing nodes and connections from the editor
        await this.editorRef.clearEditor();

        // Load the node elements into the editor from the saved design
        await this.loadElementsFromJSON(designData.elements);

        // Load the connections between nodes, if they exist
        await this.loadConnectionsFromJSON(designData.connections || []);
      },
      (error: any) => {

        // Handle any error that occurred during scenario retrieval
        const errorMsg = error?.error?.error || 'Unexpected error';
        alert('Error loading scenario: ' + JSON.stringify(errorMsg));
      }
    );
  }

  /**
   * @summary Loads and adds elements (nodes) into the editor based on saved JSON data.
   * 
   * This function iterates over an array of saved elements, retrieves their metadata from the config,
   * adds them to the editor at the specified positions, and restores their parameters.
   * 
   * Special handling is applied for specific node types like CSV, SHAP, and code-based nodes.
   * 
   * @param savedElements - An array of elements (nodes) to be restored into the editor
   * 
   * @returns A promise that resolves once all elements have been processed and added
   */
  private async loadElementsFromJSON(savedElements: any[]): Promise<void> {

    // Retrieve node display info (label and icon) from config
    savedElements.forEach(async (element: any) => {
      const nodeInfo = this.findElementInfoByType(element.type);

      // Skip if the type is not recognized in the configuration
      if (!nodeInfo) {
        return;
      }
    
      const { displayName, icon } = nodeInfo;
    
      // Add the element visually into the editor at the given position
      const node = await this.editorRef.addElement(element.type, [element.position.left, element.position.top], displayName, icon, element.id);
      
      // Restore and handle parameters specific to CSV nodes (e.g., column structure)
      if (element.type === 'CSV' && element.parameters?.columns) {
        this.elementParameters[element.id] = {
          ...element.parameters,
          columns: element.parameters.columns 
        };
      }

      // Restore selected classes for SHAP nodes
      if (element.type === 'SHAP' && element.parameters?.selectedClasses) {
        this.elementParameters[element.id] = {
          ...element.parameters,
          classes: element.parameters.selectedClasses.map((cls: any) => ({
            name: cls.name,
            selected: true
          }))
        };
      }
      
      // Restore code content for custom code nodes
      if ((element === 'CodeProcessing' || element === 'CodeSplitter') && element.parameters?.code) {
          this.elementParameters[element.id] = {
            ...element.parameters,
            code: element.parameters.code
          };
      }
      else {

        // Default restoration of parameters for any other node type
        this.elementParameters[element.id] = element.parameters;
      }
    });

    // Mark editor state as unsaved after loading elements
    this.updateUnsavedState();
  }

  /**
   * @summary Reconnects nodes in the editor using saved connection data.
   * 
   * This function uses the editor reference to recreate all connections between
   * nodes based on their saved identifiers.
   * 
   * @param savedConnections - An array of connection objects representing edges between nodes
   * 
   * @returns A promise that resolves once all connections are recreated
   */
  private async loadConnectionsFromJSON(savedConnections: any[]): Promise<void> {
    // Use editor's helper function to recreate visual connections between nodes
    await this.editorRef.connectNodesById(savedConnections);
  }
}
