import { ComponentFixture, TestBed } from '@angular/core/testing';

import { TimelineADComponent } from './timeline-ad.component';

describe('TimelineADComponent', () => {
  let component: TimelineADComponent;
  let fixture: ComponentFixture<TimelineADComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TimelineADComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(TimelineADComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
