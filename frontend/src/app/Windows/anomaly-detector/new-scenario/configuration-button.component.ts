// Angular core and common modules
import { Component, Input } from "@angular/core";
import { ClassicPreset } from "rete";

/**
 * @summary Custom control for Rete.js nodes representing a gear button.
 * 
 * This control is intended to be used inside a node in the Rete.js editor,
 * typically to open a configuration modal or trigger a settings action.
 */
export class GearButtonControl extends ClassicPreset.Control {

  /**
   * @summary Creates a new gear button control with a click handler.
   * 
   * @param onClick Function to execute when the gear icon is clicked
   */
  constructor(public onClick: () => void) {
    super();
  }
}

/**
 * @summary Angular component for rendering a gear icon inside Rete.js nodes.
 * 
 * This component is tied to the `GearButtonControl` and emits the `onClick` callback
 * when the gear icon is clicked. It prevents event propagation to avoid interfering
 * with node dragging or selection in the canvas.
 */
@Component({
  selector: "app-gear-button",
  template: `
    <i
      class="fas fa-cog gear-icon"
      (click)="data.onClick()"
      (pointerdown)="$event.stopPropagation()"
      (dblclick)="$event.stopPropagation()"
    ></i>
  `,
  styles: [`
    .gear-icon {
      position: absolute;
      top: 4px;
      right: 30px;
      color: white;
      cursor: pointer;
      font-size: 16px;
      z-index: 10;
    }
    .gear-icon:hover {
      color: #ccc;
    }
  `]
})
export class GearButtonComponent {
  /**
   * @summary Gear button control instance passed to the component.
   * 
   * This control provides the click logic for the gear icon.
   */
  @Input() data!: GearButtonControl;
}