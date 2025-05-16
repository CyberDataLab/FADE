import { Component, Input } from "@angular/core";
import { ClassicPreset } from "rete";

export class GearButtonControl extends ClassicPreset.Control {
  constructor(public onClick: () => void) {
    super();
  }
}

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
  @Input() data!: GearButtonControl;
}