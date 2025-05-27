import { Injector } from "@angular/core";
import { NodeEditor, GetSchemes, ClassicPreset } from "rete";
import { AreaPlugin, AreaExtensions, Area } from "rete-area-plugin";
import {
  ConnectionPlugin,
  Presets as ConnectionPresets
} from "rete-connection-plugin";
import { AngularPlugin, Presets, AngularArea2D, ControlComponent } from "rete-angular-plugin/15";

import { GearButtonComponent, GearButtonControl } from "./configuration-button.component";
import { DeleteButtonComponent, DeleteButtonControl } from "./delete-button.component";

type Schemes = GetSchemes<
  ClassicPreset.Node,
  ClassicPreset.Connection<ClassicPreset.Node, ClassicPreset.Node>
>;
type AreaExtra = AngularArea2D<Schemes>;

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

  render.addPreset(Presets.classic.setup());
  connection.addPreset(ConnectionPresets.classic.setup());

  editor.use(area);
  area.use(connection);
  area.use(render);

  AreaExtensions.simpleNodesOrder(area);
  const selection = AreaExtensions.selectableNodes(area, AreaExtensions.selector(), {
    accumulating: AreaExtensions.accumulateOnCtrl()
  });

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

    async addElement(type: string, position: [number, number], label?: string, icon?: string, id?: string) {
      const node = new ClassicPreset.Node(label ?? type);
      
      // 👉 Asigna ID personalizado si viene
      if (id) node.id = id;
    
      (node as any).data = { type, icon };
      (node as any).position = position;
    
      const input = new ClassicPreset.Input(socket);
      input.multipleConnections = true;
    
      if (type === "CSV" || type=== "Network") {
        node.addOutput(type, new ClassicPreset.Output(socket));
      } else if (type === "ClassificationMonitor" || type === "RegressionMonitor") {
        node.addInput(type, input);
      } else if (type === "DataSplitter" || type === "CodeSplitter") {
        // 👉 Nodo especial: 1 entrada y 2 salidas con texto personalizable
    
        node.addInput("input", new ClassicPreset.Input(socket));
    
        const output1 = new ClassicPreset.Output(socket, "train");
        const output2 = new ClassicPreset.Output(socket, "test");
    
        node.addOutput("train", output1);
        node.addOutput("test", output2);
    
        // Permitir personalizar los labels (texto visible)
        output1.label = "train";
        output2.label = "test";
      } else {
        node.addInput(type, input);
        
        node.addOutput(type, new ClassicPreset.Output(socket));
      }
    
      if (onConfigClick) {
        const gearControl = new GearButtonControl(() => onConfigClick(node));
        node.addControl("config", gearControl);
      }
    
      if (onDeleteClick) {
        const deleteControl = new DeleteButtonControl(() => {
          onDeleteClick(node);
        
          // 🔁 Eliminar explícitamente todas las conexiones del nodo
          const connections = editor.getConnections().filter(conn =>
            conn.source === node.id || conn.target === node.id
          );
        
          for (const connection of connections) {
            editor.removeConnection(connection.id);
          }
        
          // ❌ Eliminar el nodo
          editor.removeNode(node.id);
        
          // 🧼 Actualizar visualmente tras el ciclo de eliminación
          requestAnimationFrame(() => {
            for (const n of editor.getNodes()) {
              area.update('node', n.id);
            }
            for (const connection of editor.getConnections()) {
              area.update('connection', connection.id);
            }
            
            forceClearOrphanConnections();
            forceSafariRepaintFromDropArea(); // 🖌️ Arreglo para Safari y posibles residuos
          });
        });
        
      
        node.addControl("delete", deleteControl);
      }
    
      await editor.addNode(node);
      await area.translate(node.id, { x: position[0], y: position[1] });
    },

    async connectNodesById(connections: { startId: string; startOutput: string; endId: string; endInput: string }[]) {
      await new Promise(resolve => requestAnimationFrame(resolve)); // Espera render completo
    
      for (const { startId, startOutput, endId, endInput } of connections) {
        const startNode = this.editor.getNode(startId) as ClassicPreset.Node | undefined;
        const endNode = this.editor.getNode(endId) as ClassicPreset.Node | undefined;
    
        if (!startNode || !endNode) continue;
    
        const output = startNode.outputs[startOutput];
        const input = endNode.inputs[endInput];
    
        if (!output || !input) {
          console.warn(`Conexión omitida: salida "${startOutput}" o entrada "${endInput}" no encontrada.`);
          continue;
        }
    
        if (output.socket === input.socket) {
          const connection = new ClassicPreset.Connection(startNode, startOutput, endNode, endInput);
          await this.editor.addConnection(connection);
        }
      }
    
      AreaExtensions.zoomAt(this.area, this.editor.getNodes()); // Centra
    },
    
    async getNodeType(nodeId: string) {
      const node = editor.getNode(nodeId);
      if (node) {
        return ((node as any).data.type);
      }
    },
    
    clearEditor() {
      const nodes = editor.getNodes();
      for (const node of nodes) {
        editor.removeNode(node.id);
      }
    
      const connections = editor.getConnections();
      for (const connection of connections) {
        editor.removeConnection(connection.id);
      }
    
      requestAnimationFrame(() => {
        for (const n of editor.getNodes()) {
          area.update('node', n.id);
        }
        for (const connection of editor.getConnections()) {
          area.update('connection', connection.id);
        }
    
        forceSafariRepaintFromDropArea(); // 🔁 Forzar actualización visual
      });
    },

    destroy: () => area.destroy()
  };
}

function forceSafariRepaintFromDropArea() {
  const dropArea = document.getElementById('drop-area');
  if (!dropArea) return;

  dropArea.style.display = 'none';
  void dropArea.offsetHeight; // ← esto fuerza reflow en Safari
  dropArea.style.display = 'block';
}

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