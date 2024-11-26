import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FeatureEngineeringComponent } from './feature-engineering.component';

describe('FeatureEngineeringComponent', () => {
  let component: FeatureEngineeringComponent;
  let fixture: ComponentFixture<FeatureEngineeringComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureEngineeringComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(FeatureEngineeringComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
