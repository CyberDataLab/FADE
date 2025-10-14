// Angular core and common modules
import { Injector } from "@angular/core";
import { NodeEditor, GetSchemes, ClassicPreset } from "rete";
import { AreaPlugin, AreaExtensions } from "rete-area-plugin";
import {
  ConnectionPlugin,
  Presets as ConnectionPresets
} from "rete-connection-plugin";
import { AngularPlugin, Presets, AngularArea2D, ControlComponent } from "rete-angular-plugin/15";

// Custom components for node controls
import { GearButtonComponent, GearButtonControl } from "./configuration-button.component";
import { DeleteButtonComponent, DeleteButtonControl } from "./delete-button.component";

// Type definitions for the editor
type Schemes = GetSchemes<
  ClassicPreset.Node,
  ClassicPreset.Connection<ClassicPreset.Node, ClassicPreset.Node>
>;
type AreaExtra = AngularArea2D<Schemes>;

/**
 * @summary Initializes a Rete.js editor with plugins and configuration for Angular.
 * Supports custom controls (gear and delete), node types, and visual connections.
 *
 * @param container - The HTML element where the editor will be rendered.
 * @param injector - Angular's dependency injector.
 * @param onConfigClick - Callback when the gear (config) button is clicked on a node.
 * @param onDeleteClick - Callback when the delete button is clicked on a node.
 * 
 * @returns An object with references to editor, area, and utility methods.
 */
export async function createEditor(
  container: HTMLElement,
  injector: Injector,
  onConfigClick?: (node: ClassicPreset.Node) => void,
  onDeleteClick?: (node: ClassicPreset.Node) => void,
) {
  const socket = new ClassicPreset.Socket("socket");

  const editor = new NodeEditor<Schemes>();
  const area = new AreaPlugin<Schemes, AreaExtra>(container);
  const connection = new ConnectionPlugin<Schemes, AreaExtra>();
  const render = new AngularPlugin<Schemes, AreaExtra>({ injector });

  // Load default presets for rendering and connection
  render.addPreset(Presets.classic.setup());
  connection.addPreset(ConnectionPresets.classic.setup());

  editor.use(area);
  area.use(connection);
  area.use(render);

  // Enable node ordering and selection with Ctrl
  AreaExtensions.simpleNodesOrder(area);
  const selection = AreaExtensions.selectableNodes(area, AreaExtensions.selector(), {
    accumulating: AreaExtensions.accumulateOnCtrl()
  });

  // Customize rendering of controls
  render.addPreset(Presets.classic.setup({
    customize: {
      control(data) {
        if (data.payload instanceof GearButtonControl) {
          return GearButtonComponent;
        }
        if (data.payload instanceof DeleteButtonControl) {
          return DeleteButtonComponent;
        }
        if (data.payload instanceof ClassicPreset.InputControl) {
          return ControlComponent;
        }
        return null;
      }
    }
  }));

  // Remove connections when a node is removed
  editor.addPipe(context => {
    if (context.type === 'connectionremoved') {
      const { source, target } = context.data;

      const connections = editor.getConnections();
      for (const connection of connections) {
        if (connection.source === source && connection.target === target) {
          editor.removeConnection(connection.id);
        }
      }
    }
    return context;
  });

  return {
    editor,
    area,

    /**
     * @summary Adds a new node to the editor with given type, position, and optional ID.
     * Also configures inputs, outputs, and control buttons.
     *
     * @param type - Node type (e.g., "CSV", "SHAP", etc.)
     * @param position - Tuple with x, y coordinates
     * @param label - Optional label for the node
     * @param icon - Optional icon for the node
     * @param id - Optional manual ID for the node
     * 
     * @returns The created node
     */
    async addElement(type: string, position: [number, number], label?: string, icon?: string, id?: string) {
      const node = new ClassicPreset.Node(label ?? type);
      
      if (id) node.id = id;
    
      (node as any).data = { type, icon };
      (node as any).position = position;
    
      const input = new ClassicPreset.Input(socket);
      input.multipleConnections = true;
    
      // Add inputs and outputs based on node type
      if (type === "CSV" || type=== "Network") {
        node.addOutput(type, new ClassicPreset.Output(socket));
      } else if (type === "ClassificationMonitor" || type === "RegressionMonitor" || type === "SHAP" || type === "LIME") {
        node.addInput(type, input);
      } else if (type === "DataSplitter" || type === "CodeSplitter") {
    
        node.addInput("input", new ClassicPreset.Input(socket));
    
        const output1 = new ClassicPreset.Output(socket, "train");
        const output2 = new ClassicPreset.Output(socket, "test");
    
        node.addOutput("train", output1);
        node.addOutput("test", output2);
    
        output1.label = "train";
        output2.label = "test";
      } else {
        node.addInput(type, input);
        
        node.addOutput(type, new ClassicPreset.Output(socket));
      }
    
      // Attach gear button control
      if (onConfigClick) {
        const gearControl = new GearButtonControl(() => onConfigClick(node));
        node.addControl("config", gearControl);
      }
    
      // Attach delete button control
      if (onDeleteClick) {
        const deleteControl = new DeleteButtonControl(() => {
          onDeleteClick(node);
        
          const connections = editor.getConnections().filter(conn =>
            conn.source === node.id || conn.target === node.id
          );
        
          // Remove connections related to this node
          for (const connection of connections) {
            editor.removeConnection(connection.id);
          }
        
          editor.removeNode(node.id);
        
          requestAnimationFrame(() => {
            for (const n of editor.getNodes()) {
              area.update('node', n.id);
            }
            for (const connection of editor.getConnections()) {
              area.update('connection', connection.id);
            }
            
            forceClearOrphanConnections();
            forceSafariRepaintFromDropArea();
          });
        });
        
      
        node.addControl("delete", deleteControl);
      }
    
      await editor.addNode(node);
      await area.translate(node.id, { x: position[0], y: position[1] });

      return node;
    },

    /**
     * @summary Connects nodes based on an array of connection definitions.
     *
     * @param connections - List of objects with source/target IDs and input/output keys
     */
    async connectNodesById(connections: { startId: string; startOutput: string; endId: string; endInput: string }[]) {
      await new Promise(resolve => requestAnimationFrame(resolve));
    
      for (const { startId, startOutput, endId, endInput } of connections) {
        const startNode = this.editor.getNode(startId) as ClassicPreset.Node | undefined;
        const endNode = this.editor.getNode(endId) as ClassicPreset.Node | undefined;
    
        if (!startNode || !endNode) continue;
    
        const output = startNode.outputs[startOutput];
        const input = endNode.inputs[endInput];
    
        if (!output || !input) {
          continue;
        }
    
        if (output.socket === input.socket) {
          const connection = new ClassicPreset.Connection(startNode, startOutput, endNode, endInput);
          await this.editor.addConnection(connection);
        }
      }
    
      AreaExtensions.zoomAt(this.area, this.editor.getNodes());
    },
    
    /**
     * @sumamry Gets the type of a node given its ID.
     *
     * @param nodeId - Node ID to look up
     * 
     * @returns The node type as string
     */
    async getNodeType(nodeId: string) {
      const node = editor.getNode(nodeId);
      if (node) {
        return ((node as any).data.type);
      }
    },
    
    /**
     * @summary Clears all nodes and connections from the editor.
     */
    clearEditor() {
      const nodes = editor.getNodes();
      for (const node of nodes) {
        editor.removeNode(node.id);
      }
    
      // Remove all connections
      const connections = editor.getConnections();
      for (const connection of connections) {
        editor.removeConnection(connection.id);
      }
    
      // Force clear orphan connections from the DOM
      requestAnimationFrame(() => {
        for (const n of editor.getNodes()) {
          area.update('node', n.id);
        }
        for (const connection of editor.getConnections()) {
          area.update('connection', connection.id);
        }
    
        forceSafariRepaintFromDropArea();
      });
    },

    /**
     * @summary Destroys the editor instance and releases resources.
     */
    destroy: () => area.destroy()
  };
}

/**
 * @sumamry Fixes rendering issues in Safari by forcing a repaint of the drop area.
 */
function forceSafariRepaintFromDropArea() {
  const dropArea = document.getElementById('drop-area');
  if (!dropArea) return;

  dropArea.style.display = 'none';
  void dropArea.offsetHeight;
  dropArea.style.display = 'block';
}

/**
 * @summary Removes leftover SVG paths from orphaned connections in the DOM.
 */
function forceClearOrphanConnections() {
  const allPaths = document.querySelectorAll('path');
  const allConnections = document.querySelectorAll('.connection');

  allPaths.forEach(path => {
    const parent = path.closest('.connection');
    if (parent && !Array.from(allConnections).includes(parent)) {
      path.remove();
    }
  });
}