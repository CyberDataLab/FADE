import { Component, Input } from "@angular/core";
import { ClassicPreset } from "rete";

export class DeleteButtonControl extends ClassicPreset.Control {
  constructor(public onClick: () => void) {
    super();
  }
}

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
    @Input() data!: DeleteButtonControl;
  }
