// Angular core and common modules
import { Component, Input } from "@angular/core";
import { ClassicPreset } from "rete";

/**
 * @summary Custom control for Rete.js nodes representing a delete button.
 * 
 * This control is used inside Rete.js nodes to provide a clickable icon
 * that allows users to remove the node from the editor.
 */
export class DeleteButtonControl extends ClassicPreset.Control {

  /**
   * @summary Creates a new delete button control with a click handler.
   * 
   * @param onClick Function to execute when the delete icon is clicked
   */
  constructor(public onClick: () => void) {
    super();
  }
}

/**
 * @summary Angular component for rendering a delete icon inside Rete.js nodes.
 * 
 * This component renders a styled "X" icon (Font Awesome) and calls the `onClick`
 * handler from the control. It stops event propagation to prevent accidental node dragging.
 */
@Component({
  selector: "app-delete-button",
  template: `
    <i
      class="fa-solid fa-x delete-icon"
      (click)="data.onClick()"
      (pointerdown)="$event.stopPropagation()"
      (dblclick)="$event.stopPropagation()"
    ></i>
  `,
  styles: [`
    .delete-icon {
      position: absolute;
      top: 4px;
      right: 4px;
      color: white;
      cursor: pointer;
      font-size: 16px;
      z-index: 10;
    }
    .delete-icon:hover {
      color: #ccc;
    }
  `]
})

export class DeleteButtonComponent {
  /**
   * @summary Delete button control instance passed to the component.
   * 
   * This control provides the click logic for the delete icon.
   */
    @Input() data!: DeleteButtonControl;
  }
