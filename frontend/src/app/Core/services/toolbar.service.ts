// Angular core and common modules
import { Injectable } from '@angular/core';
import { BehaviorSubject, Subject } from 'rxjs';

/**
 * @summary Service for controlling toolbar state and triggering save actions.
 * 
 * This service manages the visibility of the save button and emits events
 * when a save action is requested by the user or the UI.
 */
@Injectable({
  providedIn: 'root'
})
export class ToolbarService {

  /** 
   * @summary Observable that tracks the visibility state of the save button.
   * `true` shows the button, `false` hides it.
   */
  private saveButtonVisible = new BehaviorSubject<boolean>(false);

  /** 
   * @summary Public observable for save button visibility.
   * Subscribe to update UI based on its visibility state.
   */
  saveButtonVisible$ = this.saveButtonVisible.asObservable();

  /**
   * @summary Subject that emits when a save is triggered by the toolbar.
   */
  private saveRequested = new Subject<void>();

  /** 
   * @summary Observable that emits when a save action is requested.
   * Components can subscribe to this to perform save logic.
   */
  saveRequested$ = this.saveRequested.asObservable();

  /**
   * @summary Sets the save button to visible in the UI.
   */
  showSaveButton() {
    this.saveButtonVisible.next(true);
  }

  /**
   * @summary Hides the save button from the UI.
   */
  hideSaveButton() {
    this.saveButtonVisible.next(false);
  }

  /**
   * @summary Emits a save request event.
   * 
   * Components listening to `saveRequested$` will be notified to perform save logic.
   */
  triggerSave() {
    this.saveRequested.next();
  }
}
