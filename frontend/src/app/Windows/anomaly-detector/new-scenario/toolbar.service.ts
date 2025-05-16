import { Injectable } from '@angular/core';
import { BehaviorSubject, Subject } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class ToolbarService {
  private saveButtonVisible = new BehaviorSubject<boolean>(false);
  saveButtonVisible$ = this.saveButtonVisible.asObservable();

  private saveRequested = new Subject<void>();
  saveRequested$ = this.saveRequested.asObservable();

  showSaveButton() {
    this.saveButtonVisible.next(true);
  }

  hideSaveButton() {
    this.saveButtonVisible.next(false);
  }

  triggerSave() {
    this.saveRequested.next();
  }
}
